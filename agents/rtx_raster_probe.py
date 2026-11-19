"""RTX rasteriser probe — render CAD triangles on CUDA, no OpenGL.

The Optimus laptop has no registered NVIDIA OpenGL ICD, so MuJoCo's GL path
lands on Intel UHD. CUDA is unaffected: CuPy 14.2 works, cc 8.6, 6144 MiB.

So rasterise ourselves. MuJoCo supplies physics and body transforms (cheap,
CPU); the RTX projects and z-buffers every triangle. This probe proves one
mesh renders correctly and measures the cost before committing to a film.
"""
import os
import struct
import time
from pathlib import Path

import numpy as np

H = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
PL = Path(os.environ.get('HERMES_AE_HOME', H / 'plugins' / 'hermes-ae'))
OUT = H / 'cache' / 'scratch' / 'rtx-probe'


def load_stl(p):
    """Binary STL -> (n,3,3) float32 vertices, (n,3) normals."""
    b = p.read_bytes()
    n = struct.unpack('<I', b[80:84])[0]
    if len(b) < 84 + n * 50:
        raise ValueError(f'{p.name}: truncated STL')
    raw = np.frombuffer(b, dtype=np.uint8, count=n * 50, offset=84).reshape(n, 50)
    rec = raw[:, :48].copy().view('<f4').reshape(n, 12)
    tri = rec.reshape(n, 4, 3)
    return tri[:, 1:, :].astype(np.float32), tri[:, 0, :].astype(np.float32)


RASTER = r'''
extern "C" __global__ void raster(
    const float* verts,   // (T,3,3) world-space triangle verts
    const float* norms,   // (T,3) world normals
    const float* mvp,     // (4,4)
    float* zbuf,          // (H,W)
    unsigned char* img,   // (H,W,3)
    const int T, const int W, const int H,
    const float cr, const float cg, const float cb)
{
    int t = blockIdx.x * blockDim.x + threadIdx.x;
    if (t >= T) return;

    float2 p[3]; float pz[3];
    for (int i = 0; i < 3; ++i) {
        float x = verts[t*9 + i*3 + 0];
        float y = verts[t*9 + i*3 + 1];
        float z = verts[t*9 + i*3 + 2];
        float cx = mvp[0]*x + mvp[1]*y + mvp[2]*z + mvp[3];
        float cy = mvp[4]*x + mvp[5]*y + mvp[6]*z + mvp[7];
        float cz = mvp[8]*x + mvp[9]*y + mvp[10]*z + mvp[11];
        float cw = mvp[12]*x + mvp[13]*y + mvp[14]*z + mvp[15];
        if (cw <= 1e-6f) return;
        p[i] = make_float2((cx/cw*0.5f+0.5f)*W, (1.0f-(cy/cw*0.5f+0.5f))*H);
        pz[i] = cz/cw;
    }
    float minx = fminf(fminf(p[0].x,p[1].x),p[2].x);
    float maxx = fmaxf(fmaxf(p[0].x,p[1].x),p[2].x);
    float miny = fminf(fminf(p[0].y,p[1].y),p[2].y);
    float maxy = fmaxf(fmaxf(p[0].y,p[1].y),p[2].y);
    int x0 = max(0,(int)floorf(minx)), x1 = min(W-1,(int)ceilf(maxx));
    int y0 = max(0,(int)floorf(miny)), y1 = min(H-1,(int)ceilf(maxy));
    if (x1 < x0 || y1 < y0) return;

    float area = (p[1].x-p[0].x)*(p[2].y-p[0].y) - (p[2].x-p[0].x)*(p[1].y-p[0].y);
    if (fabsf(area) < 1e-9f) return;
    float inv = 1.0f/area;

    // lambert against a fixed key light, plus ambient
    float nx = norms[t*3+0], ny = norms[t*3+1], nz = norms[t*3+2];
    float nl = nx*0.40f + ny*(-0.55f) + nz*0.73f;
    float shade = 0.30f + 0.70f*fmaxf(0.0f, nl);

    for (int y = y0; y <= y1; ++y) {
        for (int x = x0; x <= x1; ++x) {
            float px = x + 0.5f, py = y + 0.5f;
            float w0 = ((p[1].x-px)*(p[2].y-py) - (p[2].x-px)*(p[1].y-py))*inv;
            float w1 = ((p[2].x-px)*(p[0].y-py) - (p[0].x-px)*(p[2].y-py))*inv;
            float w2 = 1.0f - w0 - w1;
            if (w0 < 0 || w1 < 0 || w2 < 0) continue;
            float z = w0*pz[0] + w1*pz[1] + w2*pz[2];
            int idx = y*W + x;
            // atomic min on the depth bits: closest fragment wins
            unsigned int zi = __float_as_uint(z);
            unsigned int old = atomicMin((unsigned int*)&zbuf[idx], zi);
            if (zi <= old) {
                img[idx*3+0] = (unsigned char)(fminf(1.0f,cr*shade)*255);
                img[idx*3+1] = (unsigned char)(fminf(1.0f,cg*shade)*255);
                img[idx*3+2] = (unsigned char)(fminf(1.0f,cb*shade)*255);
            }
        }
    }
}
'''


def main():
    import cupy as cp
    OUT.mkdir(parents=True, exist_ok=True)
    dev = cp.cuda.Device(0)
    print(f'  device: {cp.cuda.runtime.getDeviceProperties(0)["name"].decode()}')
    print(f'  compute capability: {dev.compute_capability}')

    meshes = sorted((PL / 'model' / 'meshes').glob('*.STL'))
    print(f'  meshes available: {len(meshes)}')
    verts, norms = load_stl(meshes[0])
    print(f'  probe mesh: {meshes[0].name}  {len(verts)} triangles')

    W, Hh = 720, 720
    kern = cp.RawKernel(RASTER, 'raster')

    # proper perspective: scale the part to fit, then a real near/far depth map
    v = verts - verts.reshape(-1, 3).mean(axis=0)
    scale = 0.55 / float(np.abs(v).max())
    v *= scale
    v[:, 2] += 2.2                      # camera at origin looking down +Z
    f = 1.0 / np.tan(np.radians(45) / 2)
    near, far = 0.5, 8.0
    # ndc z in [0,1] so the uint bit-pattern atomicMin orders depth correctly
    A = far / (far - near)
    B = -near * far / (far - near)
    mvp = np.array([[f, 0, 0, 0],
                    [0, f, 0, 0],
                    [0, 0, A, B],
                    [0, 0, 1, 0]], dtype=np.float32)

    gv = cp.asarray(v.ravel())
    gn = cp.asarray(norms.ravel())
    gm = cp.asarray(mvp.ravel())
    gz = cp.full((Hh, W), np.inf, dtype=cp.float32)
    gi = cp.zeros((Hh, W, 3), dtype=cp.uint8)

    threads = 128
    blocks = (len(v) + threads - 1) // threads
    # warmup
    kern((blocks,), (threads,), (gv, gn, gm, gz, gi, len(v), W, Hh,
                                 cp.float32(0.83), cp.float32(0.69), cp.float32(0.22)))
    cp.cuda.Stream.null.synchronize()

    t0 = time.time()
    N = 20
    for i in range(N):
        gz.fill(cp.inf)
        gi.fill(0)
        kern((blocks,), (threads,), (gv, gn, gm, gz, gi, len(v), W, Hh,
                                     cp.float32(0.83), cp.float32(0.69), cp.float32(0.22)))
    cp.cuda.Stream.null.synchronize()
    dt = (time.time() - t0) / N
    img = cp.asnumpy(gi)
    print(f'  raster: {dt*1000:.2f} ms/frame for {len(v)} triangles at {W}x{Hh}')
    print(f'  non-black pixels: {(img.sum(axis=2)>0).sum()}')
    from PIL import Image
    Image.fromarray(img).save(OUT / 'probe.png')
    print(f'  {OUT/"probe.png"}')


if __name__ == '__main__':
    main()
