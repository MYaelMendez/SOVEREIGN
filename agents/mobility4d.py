#!/usr/bin/env python3
"""mobility4d — the whole walk as one 4D object. 9:16, mobility.foundation.

A trajectory is a 4D object: x, y, z, t. The mech-4d-holomesh surface already
had the right idea — stereographic projection with a `timeSlice`, and opacity
falling off with temporal distance. This applies it to REAL gait data.

Every pose of the walk is drawn at once, along the path it actually took. The
pose nearest the moving time-slice is solid; the rest dim by |t - slice|. You
see the whole motion as a single shape, and the gait's periodicity is visible
as structure rather than inferred from a scrubber.

    python mobility4d.py --trace walk.json --model-dir <dir> --out film.mp4

PERFORMANCE NOTE
    Forward kinematics on the CPU costs ~250 ms per body — far more than the
    raster. The ghost poses never change, so FK runs ONCE and the geometry is
    cached; each frame only rescales the colour table by temporal proximity.
    Recomputing FK per frame would make this ~30x slower for identical pixels.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, importlib.util, json, math, os, subprocess, sys, time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

GOLD = (212, 175, 55); VOID = (14, 16, 22); DIM = (138, 122, 63)
INK = (232, 230, 223); CYAN = (0, 204, 255); EMER = (0, 255, 157)


def ff() -> Path:
    h = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
    p = h / 'tools' / 'ffmpeg-7.1-nvenc' / 'bin'
    if p.exists():
        return p
    import shutil
    w = shutil.which('ffmpeg')
    if not w:
        raise SystemExit('ffmpeg not found')
    return Path(w).parent


def font(sz, bold=False):
    try:
        return ImageFont.truetype('C:/Windows/Fonts/consolab.ttf' if bold
                                  else 'C:/Windows/Fonts/consola.ttf', sz)
    except Exception:
        return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trace', required=True)
    ap.add_argument('--model-dir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--seconds', type=float, default=12.0)
    ap.add_argument('--fps', type=int, default=24)
    ap.add_argument('--ghosts', type=int, default=14)
    a = ap.parse_args()

    spec = importlib.util.spec_from_file_location('ra', HERE / 'rtx_asimov.py')
    ra = importlib.util.module_from_spec(spec); spec.loader.exec_module(ra)
    from rtx_raster import RtxRenderer, persp, look_at

    td = json.loads(Path(a.trace).read_text(encoding='utf-8'))
    Q = np.array(td['qpos'], np.float64)
    BASE = np.array(td['base'], np.float64) if 'base' in td else Q[:, :7]
    NT = len(Q)
    dur = float(td.get('duration_s', NT / float(td.get('fps', 24))))
    travel = float(BASE[-1, 0] - BASE[0, 0])
    jn = td['joint_names']

    md = Path(a.model_dir)
    urdf = json.loads((md / 'urdf.json').read_text(encoding='utf-8'))
    ra.MESHES = md / 'meshes'
    links = ra.load_links(urdf)
    names = list(links.keys())
    nL = len(links)
    chassis = np.array([0.78, 0.78, 0.80], np.float32)
    base_col = np.array([[1.0, 0.84, 0.0] if n == 'neck_pitch_link' else chassis
                         for n in names], np.float32)

    V0, _, _ = ra.world_tris(links, ra.transforms(urdf, {}), np.eye(4))
    lift = -float(V0[:, :, 2].min())
    span = float(V0[:, :, 2].max() - V0[:, :, 2].min())

    W, H = 720, 1280
    HDR, HUD = 92, 900
    VH = HUD - HDR
    r = RtxRenderer(W, VH)

    # ---- FK ONCE: the ghost poses are fixed for the whole film -------------
    NG = a.ghosts
    idxs = [int(i / max(1, NG - 1) * (NT - 1)) for i in range(NG)]
    print(f'  baking {NG} ghost poses (FK once, {NT} trace frames, {travel:+.4f} m)…')
    t0 = time.time()
    Vs, Ns, Ls = [], [], []
    for gi, k in enumerate(idxs):
        ang = {nm: float(Q[k, 7 + j]) for j, nm in enumerate(jn) if 7 + j < Q.shape[1]}
        M = np.eye(4, dtype=np.float32)
        M[:3, :3] = ra.rot_euler([0, 0, math.pi / 2])   # face across the frame
        M[0, 3] = float(BASE[k, 1])                      # lateral -> screen x
        M[1, 3] = -float(BASE[k, 0])                     # travel  -> depth
        M[2, 3] = float(BASE[k, 2]) + lift
        v, n, l = ra.world_tris(links, ra.transforms(urdf, ang), M)
        Vs.append(v); Ns.append(n); Ls.append(l + gi * nL)
    V = np.concatenate(Vs); N = np.concatenate(Ns); L = np.concatenate(Ls)
    COLS = np.concatenate([base_col for _ in range(NG)])
    bake = time.time() - t0
    print(f'  baked {len(V):,} triangles in {bake:.1f}s · {len(V)/2**20:.0f} MiB resident')

    # frame the whole path, not one body
    ymin, ymax = float(V[:, :, 1].min()), float(V[:, :, 1].max())
    xmin, xmax = float(V[:, :, 0].min()), float(V[:, :, 0].max())
    ctr = np.array([(xmin + xmax) / 2, (ymin + ymax) / 2, span * 0.45], np.float32)
    depth_span = max(1e-3, ymax - ymin)
    dist = max(span * 2.6, depth_span * 1.15)
    P = persp(38.0, 0.05, 200.0, aspect=W / VH)

    nf = int(round(a.seconds * a.fps))
    out = Path(a.out)
    wd = out.parent / (out.stem + '-m4'); fd = wd / 'frames'
    fd.mkdir(parents=True, exist_ok=True)
    F_T, F_B, F_M, F_S, F_X = font(30, True), font(40, True), font(22, True), font(17), font(14)

    r.render(V, N, COLS[L], P @ look_at(ctr + [dist, 0, span * 0.5], ctr))
    print(f'  rendering {nf} frames…')
    t0 = time.time(); rms = 0.0
    for i in range(nf):
        u = i / max(1, nf - 1)
        slice_t = u * dur
        # temporal proximity — the holomesh's own falloff, on real time
        prox = np.array([max(0.22, 1.0 - abs((k / max(1, NT - 1)) * dur - slice_t) / (dur * 0.26))
                         for k in idxs], np.float32)
        cols = COLS.copy()
        for gi in range(NG):
            sl = slice(gi * nL, (gi + 1) * nL)
            cols[sl] = COLS[sl] * (0.34 + 0.66 * prox[gi])
        tt = i / a.fps
        az = 0.30 + 0.16 * math.sin(tt * 0.35)
        eye = ctr + np.array([dist * math.cos(az), dist * math.sin(az), span * 0.55], np.float32)
        tr = time.time()
        img = r.render(V, N, cols[L], P @ look_at(eye, ctr))
        rms += (time.time() - tr) * 1000

        cv = Image.new('RGB', (W, H), VOID)
        cv.paste(Image.fromarray(img), (0, HDR))
        d = ImageDraw.Draw(cv, 'RGBA')
        d.rectangle([0, 0, W, HDR], fill=GOLD)
        d.text((20, 10), 'mobility.foundation', font=F_T, fill=VOID)
        d.text((20, 50), 'æææ:// · æLOCOMOTION · THE WALK AS ONE OBJECT', font=F_S, fill=(58, 48, 16))

        y = HUD + 18
        d.text((22, y), f't = {slice_t:5.2f} s', font=F_B, fill=CYAN); y += 50
        d.text((22, y), f'{NG} poses of {NT} · one 4D trajectory', font=F_M, fill=INK); y += 30
        d.text((22, y), f'x y z t — time is the fourth axis', font=F_S, fill=DIM); y += 30
        # the time axis, with the slice marked
        bx, bw = 22, W - 44
        d.rectangle([bx, y, bx + bw, y + 14], outline=(42, 36, 21))
        for gi, k in enumerate(idxs):
            xx = bx + int(k / max(1, NT - 1) * bw)
            g = int(60 + 195 * prox[gi])
            d.line([xx, y + 1, xx, y + 13], fill=(g, g, int(g * 0.4)))
        sx = bx + int(u * bw)
        d.line([sx, y - 4, sx, y + 18], fill=CYAN, width=2)
        y += 30
        d.text((22, y), f'{travel:+.4f} m base travel · min z {float(BASE[:,2].min()):.4f} m',
               font=F_S, fill=EMER)

        d.rectangle([0, H - 96, W, H], fill=(12, 13, 16, 255))
        d.text((22, H - 84), 'Menlo policy · MuJoCo contact · not mocap', font=F_S, fill=GOLD)
        d.text((22, H - 58), 'Every pose is a real qpos row. Nothing keyframed.', font=F_S, fill=INK)
        d.text((22, H - 32), f'mobility.foundation · this run: {NT} frames, {dur:.1f}s · trace-bound',
               font=F_X, fill=DIM)
        cv.save(fd / f'f{i:05d}.png')
        if i % 48 == 0:
            print(f'    {i}/{nf}  t={slice_t:.2f}s  raster {rms/(i+1):.0f} ms')

    el = time.time() - t0
    f = ff()
    subprocess.run([str(f / 'ffmpeg'), '-y', '-v', 'error', '-framerate', str(a.fps),
                    '-i', str(fd / 'f%05d.png'), '-c:v', 'h264_nvenc', '-preset', 'p5',
                    '-b:v', '9M', '-pix_fmt', 'yuv420p', '-t', f'{nf / a.fps:.3f}', str(out)],
                   check=True, timeout=1800)
    meta = {'ok': True, 'out': str(out), 'frames': nf, 'seconds': round(nf / a.fps, 3),
            'size': [W, H], 'ghosts': NG, 'triangles': len(V),
            'fk_bake_s': round(bake, 1), 'raster_ms': round(rms / nf, 1),
            'wall_s': round(el, 1), 'trace_frames': NT, 'travel_m': round(travel, 4),
            'projection': 'temporal proximity dimming — the holomesh timeSlice on real gait',
            'trace': str(Path(a.trace).name),
            'note': 'numbers are THIS trace, not the published ae-locomotion-1.0.0 proof '
                    '(which records a different run: +4.1868 m over 12.0 s)',
            'grants': False}
    (wd / 'render.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
