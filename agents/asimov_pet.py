#!/usr/bin/env python3
"""asimov_pet — a Hermes pet rendered from real Menlo CAD, deterministically.

The existing petdex gallery ships illustrated mascots. This one is the actual
robot: 1,007,041 triangles of Asimov CAD, rasterised on the RTX at 192x208,
nine animation states, six frames each. Same input, same bytes.

The pet contract (agent/pet/constants.py):
    atlas 1536x1872 = 8 cols x 9 rows of 192x208, RGBA
    FRAMES_PER_STATE = 6  (columns 6-7 are ignored by the renderer)
    rows: idle, running-right, running-left, waving, jumping,
          failed, waiting, running, review

A pet needs TRANSPARENCY. The film renderer paints a void gradient behind the
subject; here the shade pass writes alpha=0 where no triangle won the depth
test, so the mascot composites onto any terminal or desktop background.

    python asimov_pet.py --model-dir <dir> --out <pets>/asimov-cad

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, importlib.util, json, math, os, sys, time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FW, FH = 192, 208
COLS, ROWS = 8, 9
FRAMES = 6
STATE_ROWS = ["idle", "running-right", "running-left", "waving", "jumping",
              "failed", "waiting", "running", "review"]

# the shade pass, with alpha. Identical lighting to the film renderer so the
# pet and the films are the same object under the same light.
SHADE_A = r'''
extern "C" __global__ void shade_alpha(
    const unsigned long long* zid, const float* norms, const float* cols,
    unsigned char* img, const int W, const int H)
{
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= W*H) return;
    unsigned long long v = zid[i];
    unsigned int t = (unsigned int)(v & 0xFFFFFFFFULL);
    if (t == 0) {
        img[i*4+0]=0; img[i*4+1]=0; img[i*4+2]=0; img[i*4+3]=0;
        return;
    }
    t -= 1;
    float nx=norms[t*3+0], ny=norms[t*3+1], nz=norms[t*3+2];
    float key=fmaxf(0.0f, nx*0.40f + ny*(-0.55f) + nz*0.73f);
    float fill=fmaxf(0.0f, nx*(-0.6f) + ny*0.2f + nz*0.3f)*0.35f;
    float shade=0.22f + 0.78f*key + fill;
    img[i*4+0]=(unsigned char)(fminf(1.0f,cols[t*3+0]*shade)*255);
    img[i*4+1]=(unsigned char)(fminf(1.0f,cols[t*3+1]*shade)*255);
    img[i*4+2]=(unsigned char)(fminf(1.0f,cols[t*3+2]*shade)*255);
    img[i*4+3]=255;
}
'''


class PetRaster:
    """RGBA rasteriser. Same depth kernel as the films; alpha in the shade."""

    def __init__(self, w, h):
        import cupy as cp
        from rtx_raster import DEPTH
        self.cp = cp
        self.w, self.h = w, h
        self.kd = cp.RawKernel(DEPTH, 'depth_pass')
        self.ks = cp.RawKernel(SHADE_A, 'shade_alpha')
        self.zid = cp.zeros((h, w), dtype=cp.uint64)
        self.img = cp.zeros((h, w, 4), dtype=cp.uint8)

    def render(self, verts, norms, cols, mvp):
        cp = self.cp
        T = len(verts)
        gv = cp.asarray(verts.ravel(), dtype=cp.float32)
        gn = cp.asarray(norms.ravel(), dtype=cp.float32)
        gc = cp.asarray(cols.ravel(), dtype=cp.float32)
        gm = cp.asarray(mvp.ravel(), dtype=cp.float32)
        self.zid.fill(cp.uint64(0xFFFFFFFF00000000))
        th = 128
        self.kd(((T + th - 1) // th,), (th,), (gv, gm, self.zid, T, self.w, self.h))
        n = self.w * self.h
        self.ks(((n + th - 1) // th,), (th,),
                (self.zid, gn, gc, self.img, self.w, self.h))
        cp.cuda.Stream.null.synchronize()
        return cp.asnumpy(self.img)


def main():
    ap = argparse.ArgumentParser(prog='asimov_pet')
    ap.add_argument('--model-dir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--trace', default=None, help='policy trace for the walk rows')
    ap.add_argument('--head', default='255,214,0', help='head RGB — asimov yellow')
    ap.add_argument('--name', default='Asimov CAD')
    a = ap.parse_args()

    spec = importlib.util.spec_from_file_location('ra', HERE / 'rtx_asimov.py')
    ra = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ra)
    from rtx_raster import persp, look_at

    md = Path(a.model_dir)
    urdf = json.loads((md / 'urdf.json').read_text(encoding='utf-8'))
    ra.MESHES = md / 'meshes'
    links = ra.load_links(urdf)
    names = list(links.keys())
    head = tuple(int(x) for x in a.head.split(','))
    chassis = np.array([0.78, 0.78, 0.80], np.float32)
    cols = np.array([[c / 255.0 for c in head] if n == 'neck_pitch_link' else chassis
                     for n in names], np.float32)

    TR = None
    if a.trace and Path(a.trace).exists():
        td = json.loads(Path(a.trace).read_text(encoding='utf-8'))
        jn = td['joint_names']
        TR = {'names': jn, 'q': np.array(td['qpos'], np.float32)[:, 7:7 + len(jn)],
              'n': len(td['qpos'])}
        print(f'  gait: {TR["n"]} policy frames')

    V0, _, _ = ra.world_tris(links, ra.transforms(urdf, {}), np.eye(4))
    zmin, zmax = float(V0[:, :, 2].min()), float(V0[:, :, 2].max())
    lift, span = -zmin, zmax - zmin
    ctr = np.array([0, 0, span * 0.50], np.float32)
    dist = span * 2.35
    P = persp(32.0, 0.05, 80.0, aspect=FW / FH)
    r = PetRaster(FW, FH)

    def pose(angles, yaw, z_off, tilt=0.0):
        M = np.eye(4, dtype=np.float32)
        M[:3, :3] = ra.rot_euler([tilt, 0, yaw])
        M[2, 3] = lift + z_off
        return ra.world_tris(links, ra.transforms(urdf, angles), M)

    def gait_angles(ph):
        if TR is None:
            return {}
        k = int(ph * TR['n']) % TR['n']
        return {nm: float(TR['q'][k, j]) for j, nm in enumerate(TR['names'])}

    # arm joints for the wave — read the real names, never invent them
    arm = [n for n in names if 'shoulder' in n and ('pitch' in n or 'roll' in n)]
    print(f'  arm joints for waving: {arm[:4]}')

    def frame(state, k):
        u = k / FRAMES
        w = 2 * math.pi * u
        if state == 'idle':
            return pose(gait_angles(0.0), 0.30 + 0.05 * math.sin(w), 0.006 * math.sin(w))
        if state == 'waiting':
            return pose(gait_angles(0.0), 0.30 + 0.10 * math.sin(w), 0.004 * math.sin(w))
        if state in ('running', 'running-right', 'running-left'):
            yaw = {'running': 0.30, 'running-right': -0.55, 'running-left': 0.55 + math.pi}[state]
            return pose(gait_angles(u), yaw, 0.0)
        if state == 'waving':
            ang = gait_angles(0.0)
            for j in arm[:2]:
                ang[j] = -0.9 - 0.45 * math.sin(w)
            return pose(ang, 0.25, 0.004 * math.sin(w))
        if state == 'jumping':
            h = max(0.0, math.sin(math.pi * u)) * span * 0.16
            return pose(gait_angles(0.15), 0.30, h)
        if state == 'failed':
            # a slump that settles: tilt grows, body sinks, then a small shudder.
            # A static pose across six frames is not an animation state.
            e = 1.0 - math.cos(math.pi * u) * 0.5
            return pose(gait_angles(0.0), 0.30 + 0.06 * math.sin(w),
                        -span * (0.06 + 0.06 * e), tilt=0.28 + 0.22 * e)
        if state == 'review':
            return pose(gait_angles(0.0), 0.10 + 0.03 * math.sin(w), 0.0, tilt=-0.16)
        return pose({}, 0.30, 0.0)

    atlas = Image.new('RGBA', (FW * COLS, FH * ROWS), (0, 0, 0, 0))
    eye = ctr + np.array([dist, 0, span * 0.06], np.float32)
    MVP = P @ look_at(eye, ctr)
    v, n, l = frame('idle', 0)
    r.render(v, n, cols[l], MVP)                      # warmup, never published

    t0 = time.time()
    lit = []
    for ri, state in enumerate(STATE_ROWS):
        for k in range(FRAMES):
            v, n, l = frame(state, k)
            img = r.render(v, n, cols[l], MVP)
            a_px = int((img[:, :, 3] > 0).sum())
            lit.append(a_px)
            if a_px < 500:
                raise SystemExit(f'{state} frame {k}: only {a_px} opaque pixels — '
                                 'the pose is off-camera. Refusing to ship a blank pet.')
            atlas.paste(Image.fromarray(img, 'RGBA'), (k * FW, ri * FH))
        print(f'  {state:15s} 6 frames · {lit[-1]:,} opaque px in the last')
    el = time.time() - t0

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    atlas.save(out / 'spritesheet.webp', 'WEBP', lossless=True, quality=100)
    slug = out.name
    meta = {'id': slug, 'displayName': a.name,
            'description': 'Asimov CAD rendered on an RTX 3050 — 1,007,041 triangles, '
                           'nine states, deterministic. Not an illustration of the robot: the robot.',
            'spritesheetPath': 'spritesheet.webp', 'createdBy': 'tinygpu'}
    (out / 'pet.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\n  atlas {atlas.size} · {el:.1f}s · {len(v):,} tris/frame')
    print(f'  min opaque px across all 54 frames: {min(lit):,}')
    print(f'  wrote {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
