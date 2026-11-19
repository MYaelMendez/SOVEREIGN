#!/usr/bin/env python3
"""tinyCUDA — a deterministic GPU triangle rasteriser in one file.

The primitive under tinyGPU. No robot, no CAD, no scene graph: give it
triangles, normals, colours and a matrix, get pixels. Same input, same bytes,
every run.

    tinycuda doctor                 what card, and does it actually compute?
    tinycuda bench                  throughput across triangle counts
    tinycuda render mesh.stl out.png
    tinycuda render tris.npz out.png --width 1080 --height 1920

One dependency:  pip install cupy-cuda13x numpy
Optional:        pillow (to save PNG), ffmpeg (to encode)
Zero:            OpenGL, EGL, a display, a compiler, an engine, a context.

WHY IT EXISTS
    On an Optimus laptop the NVIDIA OpenGL ICD is often unregistered, so every
    GL path silently lands on the Intel iGPU. EGL is unavailable on Windows.
    CUDA is unaffected — so rasterise on the card directly.

WHY IT IS DETERMINISTIC
    A depth atomicMin followed by a separate colour write is a RACE: two
    fragments can both pass the test and write out of order. Instead pack
    depth into the high 32 bits and triangle id into the low 32 of a uint64,
    atomicMin THAT, then shade in a second pass from the winning id.

    One atomic, one winner, no read-modify-write window. Bit-identical output.

    The empty-pixel sentinel is 0xFFFFFFFF00000000, not all-ones: all-ones
    would make the low bits read as triangle 0xFFFFFFFF and index far past
    the colour buffer.

WHAT IT IS NOT
    1990s technique. Z-buffer, per-triangle flat normals, two directional
    lights. No PBR, no shadows, no BVH, no anti-aliasing, no texture mapping.
    A hardware rasteriser is ~36x faster on the same card. This exists for
    portability and determinism, not speed.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, json, struct, sys, time
from pathlib import Path

import numpy as np

DEPTH = r'''
extern "C" __global__ void depth_pass(
    const float* verts, const float* mvp,
    unsigned long long* zid,          // (H,W) packed depth<<32 | (tri+1)
    const int T, const int W, const int H)
{
    int t = blockIdx.x * blockDim.x + threadIdx.x;
    if (t >= T) return;
    float2 p[3]; float pz[3];
    for (int i = 0; i < 3; ++i) {
        float x = verts[t*9+i*3+0], y = verts[t*9+i*3+1], z = verts[t*9+i*3+2];
        float cx = mvp[0]*x+mvp[1]*y+mvp[2]*z+mvp[3];
        float cy = mvp[4]*x+mvp[5]*y+mvp[6]*z+mvp[7];
        float cz = mvp[8]*x+mvp[9]*y+mvp[10]*z+mvp[11];
        float cw = mvp[12]*x+mvp[13]*y+mvp[14]*z+mvp[15];
        if (cw <= 1e-6f) return;
        p[i] = make_float2((cx/cw*0.5f+0.5f)*W, (1.0f-(cy/cw*0.5f+0.5f))*H);
        pz[i] = cz/cw;
        if (pz[i] < 0.0f || pz[i] > 1.0f) return;
    }
    float minx=fminf(fminf(p[0].x,p[1].x),p[2].x), maxx=fmaxf(fmaxf(p[0].x,p[1].x),p[2].x);
    float miny=fminf(fminf(p[0].y,p[1].y),p[2].y), maxy=fmaxf(fmaxf(p[0].y,p[1].y),p[2].y);
    int x0=max(0,(int)floorf(minx)), x1=min(W-1,(int)ceilf(maxx));
    int y0=max(0,(int)floorf(miny)), y1=min(H-1,(int)ceilf(maxy));
    if (x1<x0 || y1<y0) return;
    float area=(p[1].x-p[0].x)*(p[2].y-p[0].y)-(p[2].x-p[0].x)*(p[1].y-p[0].y);
    if (fabsf(area)<1e-9f) return;
    float inv=1.0f/area;
    for (int y=y0; y<=y1; ++y) for (int x=x0; x<=x1; ++x) {
        float px=x+0.5f, py=y+0.5f;
        float w0=((p[1].x-px)*(p[2].y-py)-(p[2].x-px)*(p[1].y-py))*inv;
        float w1=((p[2].x-px)*(p[0].y-py)-(p[0].x-px)*(p[2].y-py))*inv;
        float w2=1.0f-w0-w1;
        if (w0<0||w1<0||w2<0) continue;
        float z=w0*pz[0]+w1*pz[1]+w2*pz[2];
        unsigned int zi=__float_as_uint(z);   // positive floats order as uints
        unsigned long long packed=((unsigned long long)zi<<32)|(unsigned long long)(t+1);
        atomicMin(&zid[y*W+x], packed);
    }
}
'''

SHADE = r'''
extern "C" __global__ void shade_pass(
    const unsigned long long* zid, const float* norms, const float* cols,
    unsigned char* img, const int W, const int H,
    const float bg_r, const float bg_g, const float bg_b)
{
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= W*H) return;
    unsigned long long v = zid[i];
    unsigned int t = (unsigned int)(v & 0xFFFFFFFFULL);
    if (t == 0) {
        float gy = (float)(i / W) / (float)H;
        img[i*3+0]=(unsigned char)(bg_r*(0.35f+0.65f*gy)*255);
        img[i*3+1]=(unsigned char)(bg_g*(0.35f+0.65f*gy)*255);
        img[i*3+2]=(unsigned char)(bg_b*(0.35f+0.65f*gy)*255);
        return;
    }
    t -= 1;
    float nx=norms[t*3+0], ny=norms[t*3+1], nz=norms[t*3+2];
    float key=fmaxf(0.0f, nx*0.40f + ny*(-0.55f) + nz*0.73f);
    float fill=fmaxf(0.0f, nx*(-0.6f) + ny*0.2f + nz*0.3f)*0.35f;
    float shade=0.22f + 0.78f*key + fill;
    img[i*3+0]=(unsigned char)(fminf(1.0f,cols[t*3+0]*shade)*255);
    img[i*3+1]=(unsigned char)(fminf(1.0f,cols[t*3+1]*shade)*255);
    img[i*3+2]=(unsigned char)(fminf(1.0f,cols[t*3+2]*shade)*255);
}
'''


def load_stl(p: Path):
    """Binary STL -> (triangles[N,3,3], normals[N,3]). ASCII is not supported."""
    b = Path(p).read_bytes()
    if len(b) < 84:
        raise ValueError(f'{p}: too short for a binary STL')
    n = struct.unpack('<I', b[80:84])[0]
    if len(b) < 84 + n * 50:
        raise ValueError(f'{p}: truncated — header says {n} triangles')
    raw = np.frombuffer(b, dtype=np.uint8, count=n * 50, offset=84).reshape(n, 50)
    rec = raw[:, :48].copy().view('<f4').reshape(n, 12)
    tri = rec.reshape(n, 4, 3)
    v = tri[:, 1:, :].astype(np.float32)
    nrm = tri[:, 0, :].astype(np.float32)
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.divide(nrm, ln, out=np.zeros_like(nrm), where=ln > 1e-9)
    return v, nrm


def persp(fov_deg, near, far, aspect=1.0):
    f = 1.0 / np.tan(np.radians(fov_deg) / 2)
    A = far / (far - near)
    B = -near * far / (far - near)
    return np.array([[f / aspect, 0, 0, 0], [0, f, 0, 0],
                     [0, 0, A, B], [0, 0, 1, 0]], dtype=np.float32)


def look_at(eye, target, up=(0, 0, 1)):
    eye = np.asarray(eye, np.float32); target = np.asarray(target, np.float32)
    fwd = target - eye; fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, np.asarray(up, np.float32)); right /= np.linalg.norm(right)
    u = np.cross(right, fwd)
    R = np.stack([right, u, fwd], axis=0)     # camera looks down +Z
    M = np.eye(4, dtype=np.float32)
    M[:3, :3] = R
    M[:3, 3] = -R @ eye
    return M


def fit_camera(v, fov=40.0, az=0.9, el=0.45):
    """Frame any triangle soup: centre it, back off by its radius."""
    pts = v.reshape(-1, 3)
    ctr = pts.mean(axis=0)
    rad = float(np.linalg.norm(pts - ctr, axis=1).max()) or 1.0
    d = rad * 2.8
    eye = ctr + np.array([d*np.cos(az)*np.cos(el), d*np.sin(az)*np.cos(el),
                          d*np.sin(el)], np.float32)
    return persp(fov, rad*0.02, rad*12) @ look_at(eye, ctr), ctr, rad


class Raster:
    """Deterministic CUDA triangle rasteriser.

    colours are 0-1 floats. Passing 0-255 saturates every pixel to white —
    a valid image with correct geometry that looks like a flat silhouette.
    """

    def __init__(self, w, h):
        import cupy as cp
        self.cp = cp
        self.w, self.h = int(w), int(h)
        self.kd = cp.RawKernel(DEPTH, 'depth_pass')
        self.ks = cp.RawKernel(SHADE, 'shade_pass')
        self.zid = cp.zeros((self.h, self.w), dtype=cp.uint64)
        self.img = cp.zeros((self.h, self.w, 3), dtype=cp.uint8)

    def render(self, verts, norms, cols, mvp, bg=(0.02, 0.03, 0.05)):
        cp = self.cp
        verts = np.ascontiguousarray(verts, np.float32)
        norms = np.ascontiguousarray(norms, np.float32)
        cols = np.ascontiguousarray(cols, np.float32)
        T = len(verts)
        if not (len(norms) == len(cols) == T):
            raise ValueError(f'length mismatch: {T} verts, {len(norms)} norms, {len(cols)} cols')
        gv = cp.asarray(verts.ravel()); gn = cp.asarray(norms.ravel())
        gc = cp.asarray(cols.ravel())
        gm = cp.asarray(np.ascontiguousarray(mvp, np.float32).ravel())
        # depth = max, id = 0. All-ones would read as triangle 0xFFFFFFFF.
        self.zid.fill(cp.uint64(0xFFFFFFFF00000000))
        th = 128
        if T:
            self.kd(((T + th - 1)//th,), (th,), (gv, gm, self.zid, T, self.w, self.h))
        n = self.w * self.h
        self.ks(((n + th - 1)//th,), (th,),
                (self.zid, gn, gc, self.img, self.w, self.h,
                 cp.float32(bg[0]), cp.float32(bg[1]), cp.float32(bg[2])))
        cp.cuda.Stream.null.synchronize()
        return cp.asnumpy(self.img)


def doctor() -> dict:
    out = {'ok': False, 'checks': {}}
    try:
        import cupy as cp
        p = cp.cuda.runtime.getDeviceProperties(0)
        sm = p['multiProcessorCount']; ghz = p['clockRate']/1e6
        out['checks']['cuda'] = {
            'device': p['name'].decode() if isinstance(p['name'], bytes) else str(p['name']),
            'compute_capability': f"{p['major']}.{p['minor']}",
            'vram_gb': round(p['totalGlobalMem']/1e9, 2), 'sms': sm,
            'tflops_fp32': round(sm*128*2*ghz/1000, 1)}
        a = cp.random.rand(1024, 1024, dtype=cp.float32)
        cp.cuda.Stream.null.synchronize()
        t0 = time.perf_counter()
        for _ in range(10):
            a = a @ a
        cp.cuda.Stream.null.synchronize()
        dt = (time.perf_counter()-t0)/10
        out['checks']['matmul'] = {'ms': round(dt*1000, 2),
                                   'gflops': round(2*1024**3/dt/1e9, 1)}
        # compile the kernels — a card that enumerates but cannot JIT is not usable
        r = Raster(64, 64)
        v = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]], np.float32)
        n = np.array([[0, 0, 1]], np.float32)
        c = np.array([[0.8, 0.7, 0.2]], np.float32)
        r.render(v, n, c, np.eye(4, dtype=np.float32))
        out['checks']['kernels'] = 'compiled and ran'
        out['ok'] = True
    except Exception as exc:
        out['checks']['cuda'] = {'error': f'{type(exc).__name__}: {exc}',
                                 'fix': 'pip install cupy-cuda13x (match your CUDA major)'}
    out['deps'] = 'pip install cupy-cuda13x numpy'
    out['opengl_required'] = False
    out['note'] = 'measured on this machine, not assumed'
    return out


def _synthetic(n_tri, seed=0):
    """A reproducible triangle soup for benchmarking — no asset needed."""
    rng = np.random.default_rng(seed)
    ctr = rng.uniform(-1, 1, (n_tri, 3)).astype(np.float32)
    off = rng.uniform(-0.03, 0.03, (n_tri, 3, 3)).astype(np.float32)
    v = ctr[:, None, :] + off
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 1e-9).astype(np.float32)
    c = rng.uniform(0.2, 1.0, (n_tri, 3)).astype(np.float32)
    return v, n, c


def bench(sizes=(1_000, 10_000, 100_000, 1_000_000), w=720, h=1280, reps=5) -> dict:
    r = Raster(w, h)
    rows = []
    for n in sizes:
        v, nm, c = _synthetic(n)
        M, _, _ = fit_camera(v)
        r.render(v, nm, c, M)                      # warmup: first JIT is not throughput
        t0 = time.perf_counter()
        for _ in range(reps):
            px = r.render(v, nm, c, M)
        dt = (time.perf_counter()-t0)/reps
        rows.append({'triangles': n, 'ms': round(dt*1000, 2),
                     'fps': round(1/dt, 1), 'mtri_per_s': round(n/dt/1e6, 2)})
    return {'ok': True, 'resolution': [w, h], 'reps': reps, 'rows': rows,
            'note': 'warmup discarded; the first render includes kernel JIT'}


def render_file(src: Path, out: Path, w=720, h=1280, fov=40.0,
                colour=(0.83, 0.69, 0.22)) -> dict:
    src = Path(src)
    if src.suffix.lower() == '.stl':
        v, n = load_stl(src)
    elif src.suffix.lower() == '.npz':
        d = np.load(src)
        v, n = d['verts'], d['norms']
    else:
        return {'ok': False, 'reason': f'unsupported input {src.suffix}; use .stl or .npz'}
    c = np.tile(np.array(colour, np.float32), (len(v), 1))
    M, ctr, rad = fit_camera(v, fov=fov)
    r = Raster(w, h)
    r.render(v, n, c, M)
    t0 = time.perf_counter()
    px = r.render(v, n, c, M)
    dt = time.perf_counter()-t0
    try:
        from PIL import Image
        Image.fromarray(px).save(out)
        saved = str(out)
    except Exception:
        np.save(out.with_suffix('.npy'), px); saved = str(out.with_suffix('.npy'))
    import hashlib
    return {'ok': True, 'triangles': len(v), 'resolution': [w, h],
            'ms': round(dt*1000, 2), 'file': saved,
            'sha256': hashlib.sha256(px.tobytes()).hexdigest(),
            'mean_luminance': round(float(px.mean()), 2),
            'note': 'colours are 0-1; the hash is over the raw pixel buffer'}


def main():
    ap = argparse.ArgumentParser(prog='tinycuda', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor')
    b = sub.add_parser('bench')
    b.add_argument('--width', type=int, default=720)
    b.add_argument('--height', type=int, default=1280)
    b.add_argument('--reps', type=int, default=5)
    r = sub.add_parser('render')
    r.add_argument('src'); r.add_argument('out')
    r.add_argument('--width', type=int, default=720)
    r.add_argument('--height', type=int, default=1280)
    r.add_argument('--fov', type=float, default=40.0)
    a = ap.parse_args()
    if a.cmd == 'doctor':
        res = doctor()
    elif a.cmd == 'bench':
        res = bench(w=a.width, h=a.height, reps=a.reps)
    else:
        res = render_file(Path(a.src), Path(a.out), a.width, a.height, a.fov)
    print(json.dumps(res, indent=2))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
