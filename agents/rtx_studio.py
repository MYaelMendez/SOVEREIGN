"""rtx_studio — the whole Asimov rendered on the RTX, no OpenGL.

MuJoCo supplies physics and per-body transforms on CPU (cheap). Every CAD
triangle is transformed to world space and rasterised on the RTX with CuPy
RawKernels. The Optimus laptop has no registered NVIDIA OpenGL ICD, so this
path is the only way to get the discrete GPU drawing frames here.

    python rtx_studio.py --spec spec.json --out film.mp4 [--frames N]

Determinism: same spec -> same frames. Depth is resolved by a packed
uint64 atomicMin (depth<<32 | tri+1), so there is no fragment race.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rtx_raster import RtxRenderer, load_stl, persp, look_at  # noqa: E402

H = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
PL = Path(os.environ.get('HERMES_AE_HOME', H / 'plugins' / 'hermes-ae'))
FF = H / 'tools' / 'ffmpeg-7.1-nvenc' / 'bin'
PY = os.environ.get('HERMES_AE_PYTHON', sys.executable)

W, HH = 720, 1280
HDR, VH = 92, 720
HUD = HDR + VH

STATE_RGB = {
    'IDLE': (150, 150, 155), 'LISTENING': (0, 204, 255), 'SPEAKING': (0, 255, 159),
    'THINKING': (133, 233, 252), 'AWAITING_APPROVAL': (212, 175, 55),
    'APPROVED': (0, 255, 159), 'REFUSED': (255, 0, 255), 'ERROR': (255, 59, 71),
}


def capsule_tris(radius, half, nu=16, nv=8):
    """Capsule along local Z: cylinder + two hemispheres, as triangles."""
    pts, nrm = [], []
    def ring(z, r):
        return [(r * np.cos(2 * np.pi * i / nu), r * np.sin(2 * np.pi * i / nu), z)
                for i in range(nu)]
    # cylinder wall
    lo, hi = ring(-half, radius), ring(half, radius)
    for i in range(nu):
        j = (i + 1) % nu
        a, b, c, d = lo[i], lo[j], hi[j], hi[i]
        for tri in ((a, b, c), (a, c, d)):
            pts.append(tri)
            n = np.array([np.cos(2 * np.pi * i / nu), np.sin(2 * np.pi * i / nu), 0.0])
            nrm.append(n)
    # hemispheres
    for sign, zc in ((1, half), (-1, -half)):
        for k in range(nv):
            t0 = (np.pi / 2) * k / nv
            t1 = (np.pi / 2) * (k + 1) / nv
            for i in range(nu):
                a0, a1 = 2 * np.pi * i / nu, 2 * np.pi * ((i + 1) % nu) / nu
                def P(t, a):
                    st, ct = np.sin(t), np.cos(t)
                    return (radius * ct * np.cos(a), radius * ct * np.sin(a),
                            zc + sign * radius * st)
                p00, p01, p11, p10 = P(t0, a0), P(t0, a1), P(t1, a1), P(t1, a0)
                for tri in ((p00, p01, p11), (p00, p11, p10)):
                    pts.append(tri)
                    ctr = np.mean(tri, axis=0) - np.array([0, 0, zc])
                    ln = np.linalg.norm(ctr)
                    nrm.append(ctr / ln if ln > 1e-9 else np.array([0, 0, sign]))
    return np.asarray(pts, np.float32), np.asarray(nrm, np.float32)


def sphere_tris(radius, nu=14, nv=8):
    pts, nrm = [], []
    for k in range(nv):
        t0 = -np.pi / 2 + np.pi * k / nv
        t1 = -np.pi / 2 + np.pi * (k + 1) / nv
        for i in range(nu):
            a0, a1 = 2 * np.pi * i / nu, 2 * np.pi * ((i + 1) % nu) / nu
            def P(t, a):
                return (radius * np.cos(t) * np.cos(a), radius * np.cos(t) * np.sin(a),
                        radius * np.sin(t))
            p00, p01, p11, p10 = P(t0, a0), P(t0, a1), P(t1, a1), P(t1, a0)
            for tri in ((p00, p01, p11), (p00, p11, p10)):
                pts.append(tri)
                ctr = np.mean(tri, axis=0)
                ln = np.linalg.norm(ctr)
                nrm.append(ctr / ln if ln > 1e-9 else np.array([0, 0, 1]))
    return np.asarray(pts, np.float32), np.asarray(nrm, np.float32)


def build_world():
    """Compile the model and map every geom's mesh to its body transform."""
    import mujoco
    src = (PL / 'model/xml/asimov_1_25dof_actuated.xml').read_text(encoding='utf-8')
    src = re.sub(r'meshdir="[^"]*"', f'meshdir="{(PL/"model/meshes").as_posix()}"', src)
    m = mujoco.MjSpec.from_string(src).compile()
    d = mujoco.MjData(m)
    d.ctrl[:] = np.clip(0.0, m.actuator_ctrlrange[:, 0], m.actuator_ctrlrange[:, 1])
    for _ in range(900):
        mujoco.mj_step(m, d)
    mujoco.mj_forward(m, d)

    # mesh id -> local vertices/normals, and the mesh's own frame offset
    meshes = {}
    for i in range(m.nmesh):
        name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_MESH, i)
        if not name:
            continue
        # MuJoCo mesh names here INCLUDE the extension ('pelvis.STL'), so use
        # the name as a filename first and only append .STL if it has no suffix.
        p = PL / 'model' / 'meshes' / name
        if not p.exists():
            p = PL / 'model' / 'meshes' / f'{name}.STL'
        if not p.exists():
            cand = [q for q in (PL / 'model' / 'meshes').iterdir()
                    if q.stem.lower() == Path(name).stem.lower()]
            if not cand:
                continue
            p = cand[0]
        v, n = load_stl(p)
        # MuJoCo recentres meshes by their inertia frame; replicate via mesh_pos/quat
        mp = m.mesh_pos[i].astype(np.float32)
        mq = m.mesh_quat[i].astype(np.float32)
        R = np.zeros(9, np.float64)
        mujoco.mju_quat2Mat(R, mq.astype(np.float64))
        R = R.reshape(3, 3).astype(np.float32)
        v = (v @ R.T) + mp
        n = (n @ R.T)
        meshes[i] = (v, n)

    # geom -> tessellated local triangles. Meshes come from STL; capsules and
    # spheres are generated, because the torso, neck and arm joints are
    # PRIMITIVES in this model — skipping them leaves a hollow, floating robot.
    geoms = []
    prims = {}
    for g in range(m.ngeom):
        gt = int(m.geom_type[g])
        if gt == mujoco.mjtGeom.mjGEOM_MESH:
            mid = m.geom_dataid[g]
            if mid < 0 or mid not in meshes:
                continue
            geoms.append((g, meshes[mid]))
        elif gt == mujoco.mjtGeom.mjGEOM_CAPSULE:
            r, half = float(m.geom_size[g][0]), float(m.geom_size[g][1])
            key = ('cap', round(r, 4), round(half, 4))
            if key not in prims:
                prims[key] = capsule_tris(r, half)
            geoms.append((g, prims[key]))
        elif gt == mujoco.mjtGeom.mjGEOM_SPHERE:
            r = float(m.geom_size[g][0])
            key = ('sph', round(r, 4))
            if key not in prims:
                prims[key] = sphere_tris(r)
            geoms.append((g, prims[key]))
        # PLANE is the floor; the shader's background gradient stands in for it
    return m, d, meshes, geoms


def world_tris(m, d, meshes, geoms):
    """Transform every geom's triangles into world space for this pose."""
    Vs, Ns, Gs = [], [], []
    for g, (v, n) in geoms:
        R = d.geom_xmat[g].reshape(3, 3).astype(np.float32)
        t = d.geom_xpos[g].astype(np.float32)
        Vs.append(v @ R.T + t)
        Ns.append(n @ R.T)
        Gs.append(np.full(len(v), g, np.int32))
    return (np.concatenate(Vs).astype(np.float32),
            np.concatenate(Ns).astype(np.float32),
            np.concatenate(Gs))


def geom_colors(m, geoms, head_rgb, body_rgb=(0.86, 0.87, 0.90)):
    """Head geoms take the state colour; the rest are the chassis."""
    hb = m.body('neck_pitch_link').id
    cols = np.zeros((m.ngeom, 3), np.float32)
    for g in range(m.ngeom):
        cols[g] = np.array(head_rgb, np.float32) / 255 if m.geom_bodyid[g] == hb \
            else np.array(body_rgb, np.float32)
    return cols


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--frames', type=int, default=0, help='cap frames (0 = full)')
    ap.add_argument('--workdir')
    a = ap.parse_args()

    import cupy as cp
    from PIL import Image, ImageDraw, ImageFont
    import mujoco

    spec = json.loads(Path(a.spec).read_text(encoding='utf-8'))
    out = Path(a.out)
    wd = Path(a.workdir) if a.workdir else out.parent / (out.stem + '-rtx')
    fd = wd / 'frames'
    fd.mkdir(parents=True, exist_ok=True)

    print(f'  device: {cp.cuda.runtime.getDeviceProperties(0)["name"].decode()}')
    m, d, meshes, geoms = build_world()
    print(f'  meshes {len(meshes)}  mesh-geoms {len(geoms)}')
    v0, n0, g0 = world_tris(m, d, meshes, geoms)
    print(f'  world triangles: {len(v0)}')

    base_q = d.qpos.copy()
    ay = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, 'neck_yaw_joint')
    ap_ = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, 'neck_pitch_joint')
    AY = int(m.jnt_qposadr[ay]) if ay >= 0 else None
    AP = int(m.jnt_qposadr[ap_]) if ap_ >= 0 else None

    fps = int(spec.get('fps', 24))
    scenes = spec['scenes']
    # scene durations from the spec's own audio if present, else 4s each
    t = 0.0
    for s in scenes:
        dur = float(s.get('_dur', 4.0))
        s['_t0'] = t; s['_t1'] = t + dur; t += dur
    total = t
    nf = int(round(total * fps))
    if a.frames:
        nf = min(nf, a.frames)
    print(f'  {nf} frames @ {fps}fps  ({total:.2f}s)')

    r = RtxRenderer(W, VH)
    ident = spec.get('identity', [0, 170, 255])
    P = persp(45, 0.05, 40.0, aspect=W / VH)

    def font(sz, bold=False):
        p = f"C:/Windows/Fonts/{'consolab' if bold else 'consola'}.ttf"
        return ImageFont.truetype(p, sz) if Path(p).exists() else ImageFont.load_default()
    F_B, F_M, F_S, F_X = font(30, True), font(22, True), font(19), font(17)

    # warmup so the first saved frame is not a compile artefact
    cols = geom_colors(m, geoms, ident)
    tc = cols[g0]
    eye = np.array([2.4, 0.0, 1.05], np.float32)
    r.render(v0, n0, tc, P @ look_at(eye, [0, 0, 0.95]))

    t0 = time.time()
    raster_ms = 0.0
    for i in range(nf):
        tt = i / fps
        s = scenes[0]
        for sc in scenes:
            if sc['_t0'] <= tt < sc['_t1']:
                s = sc; break
        if tt >= scenes[-1]['_t1']:
            s = scenes[-1]
        stt = s.get('state', 'SPEAKING')
        rgb = STATE_RGB.get(stt, (212, 175, 55))
        head = tuple(int(ident[k] * 0.78 + rgb[k] * 0.22) for k in range(3))

        d.qpos[:] = base_q
        if AY is not None:
            d.qpos[AY] = 0.05 * np.sin(tt * 1.3)
        mujoco.mj_forward(m, d)
        V, N, G = world_tris(m, d, meshes, geoms)
        cols = geom_colors(m, geoms, head)
        az = np.radians(float(spec.get('azimuth', 0)) + 4 * np.sin(tt * 0.4))
        dist = float(spec.get('distance', 2.5))
        eye = np.array([dist * np.cos(az), dist * np.sin(az),
                        float(spec.get('lookat_z', 0.95)) + 0.18], np.float32)
        M = P @ look_at(eye, [0, 0, float(spec.get('lookat_z', 0.95))])
        tr = time.time()
        img = r.render(V, N, cols[G], M)
        raster_ms += (time.time() - tr) * 1000

        canvas = Image.new('RGB', (W, HH), (11, 10, 6))
        canvas.paste(Image.fromarray(img), (0, HDR))
        dr = ImageDraw.Draw(canvas, 'RGBA')
        dr.rectangle([0, 0, W, HDR], fill=(212, 175, 55, 255))
        dr.text((26, 14), spec.get('title', 'æ://'), font=F_B, fill=(11, 10, 6, 255))
        dr.text((26, 54), spec.get('tagline', 'RTX RASTERISED · CUDA'), font=F_S, fill=(58, 48, 16, 255))
        dr.rectangle([0, HUD, W, HH], fill=(14, 13, 8, 255))
        dr.rectangle([0, HUD, W, HUD + 5], fill=rgb + (255,))
        y = HUD + 18
        if s.get('kicker'):
            dr.text((26, y), s['kicker'][:46], font=F_X, fill=(201, 179, 106, 255)); y += 30
        if s.get('banner'):
            dr.rectangle([20, y, W - 20, y + 44], fill=rgb + (255,))
            dr.text((32, y + 10), s['banner'][:28], font=F_M, fill=(11, 10, 6, 255)); y += 56
        for ln in s.get('lines', [])[:4]:
            dr.text((26, y), ln[:48], font=F_S, fill=(255, 246, 218, 255)); y += 28
        y += 10
        sp = s.get('speak', '')
        line = ''
        for w_ in sp.split():
            if dr.textlength(line + w_, font=F_X) > W - 52:
                dr.text((26, y), line, font=F_X, fill=(180, 168, 130, 255)); y += 26; line = w_ + ' '
            else:
                line += w_ + ' '
            if y > HH - 60:
                break
        if y <= HH - 60:
            dr.text((26, y), line, font=F_X, fill=(180, 168, 130, 255))
        dr.text((26, HH - 40), spec.get('footer', 'RTX:// CUDA · HUMAN://ROOT'),
                font=F_X, fill=(138, 122, 63, 255))
        canvas.save(fd / f'f{i:05d}.png')
        if i % 60 == 0:
            print(f'  {i}/{nf} t={tt:.2f} {stt}')

    el = time.time() - t0
    print(f'  rendered {nf} frames in {el:.1f}s  ({el/nf*1000:.0f} ms/frame total)')
    print(f'  raster only: {raster_ms/nf:.1f} ms/frame  ({1000/(raster_ms/nf):.0f} fps)')

    silent = wd / 'silent.mp4'
    subprocess.run([str(FF / 'ffmpeg.exe'), '-v', 'error', '-y', '-framerate', str(fps),
                    '-i', str(fd / 'f%05d.png'), '-c:v', 'h264_nvenc', '-preset', 'p5',
                    '-b:v', '6M', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                    str(silent)], capture_output=True, timeout=1800)
    silent.replace(out)
    meta = dict(frames=nf, fps=fps, total_s=round(total, 3), seconds=round(el, 1),
                ms_per_frame=round(el / nf * 1000, 1),
                raster_ms=round(raster_ms / nf, 1), triangles=len(v0),
                device='RTX 3050 CUDA', bytes=out.stat().st_size)
    (wd / 'rtx.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(f'  {out}  {out.stat().st_size} bytes')
    print('  ' + json.dumps(meta))


if __name__ == '__main__':
    main()
