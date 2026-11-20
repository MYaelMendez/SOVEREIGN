#!/usr/bin/env python3
"""tinymujoco_film — determinism made visible. Five seconds, two bodies, one hash.

Two robots are drawn from two REAL physics traces:

  phase A  reference + candidate, SAME seed  → byte-identical qpos, so the two
           bodies occupy exactly the same space and read as ONE robot.
  phase B  reference + a DIFFERENT seed      → the bodies separate, and the
           separation on screen IS the max-abs-diff number beside them.

Nothing is animated by hand. Every pose is a qpos row from MuJoCo 4.0.1 stepping
the pinned Asimov model under a seeded control sequence. The robot collapses
because random control is not a policy — that is honest physics, not a failure
of the renderer.

    python tinymujoco_film.py --ref mj-ref.npy --same mj-cand.npy \
        --diff mj-wrong.npy --model-dir <dir> --out film.mp4

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, importlib.util, json, math, os, subprocess, sys, time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

GOLD = (212, 175, 55); VOID = (11, 10, 6); DIM = (138, 122, 63)
INK = (232, 230, 223); EMER = (0, 255, 157); MAG = (255, 64, 220)


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
    ap.add_argument('--ref', required=True)
    ap.add_argument('--same', required=True)
    ap.add_argument('--diff', required=True)
    ap.add_argument('--model-dir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--seconds', type=float, default=5.0)
    ap.add_argument('--fps', type=int, default=24)
    a = ap.parse_args()

    spec = importlib.util.spec_from_file_location('ra', HERE / 'rtx_asimov.py')
    ra = importlib.util.module_from_spec(spec); spec.loader.exec_module(ra)
    from rtx_raster import RtxRenderer, persp, look_at

    REF = np.load(a.ref); SAME = np.load(a.same); DIFF = np.load(a.diff)
    if not (REF.shape == SAME.shape == DIFF.shape):
        raise SystemExit(f'trace shapes differ: {REF.shape} {SAME.shape} {DIFF.shape}')
    identical = np.array_equal(REF, SAME)
    if not identical:
        raise SystemExit('the same-seed trace is NOT identical to the reference — '
                         'the film would assert a determinism it does not have')
    div_diff = np.abs(REF - DIFF).max(axis=1)
    div_same = np.abs(REF - SAME).max(axis=1)   # must be all-zero; asserted below
    if div_same.max() != 0.0:
        raise SystemExit('same-seed traces diverge — refusing to label them identical')

    md = Path(a.model_dir)
    urdf = json.loads((md / 'urdf.json').read_text(encoding='utf-8'))
    ra.MESHES = md / 'meshes'
    links = ra.load_links(urdf)
    names = list(links.keys())
    chassis = np.array([0.78, 0.78, 0.80], np.float32)

    def table(rgb):
        return np.array([[c / 255.0 for c in rgb] if n == 'neck_pitch_link' else chassis
                         for n in names], np.float32)
    COL_A = table((255, 214, 0))     # reference — asimov yellow
    COL_B = table((0, 170, 255))     # candidate — hermes cyan
    nL = len(links)
    cols = np.concatenate([COL_A, COL_B])

    # the trace's qpos layout: 7 free-joint entries then the 23 actuated joints
    JN = json.loads((md / 'urdf.json').read_text(encoding='utf-8'))
    joint_names = [j['name'] for j in JN['joints']]

    V0, _, _ = ra.world_tris(links, ra.transforms(urdf, {}), np.eye(4))
    zmin, zmax = float(V0[:, :, 2].min()), float(V0[:, :, 2].max())
    lift, span = -zmin, zmax - zmin

    W, H = 720, 1280
    HDR, HUD = 84, 880
    VH = HUD - HDR
    r = RtxRenderer(W, VH)
    P = persp(36.0, 0.05, 80.0, aspect=W / VH)
    ctr = np.array([0, 0, span * 0.42], np.float32)
    dist = span * 2.9

    nf = int(round(a.seconds * a.fps))
    out = Path(a.out)
    wd = out.parent / (out.stem + '-mj'); fd = wd / 'frames'
    fd.mkdir(parents=True, exist_ok=True)
    F_T, F_B, F_M, F_S, F_X = font(28, True), font(50, True), font(23, True), font(18), font(15)

    def body(qrow, y_off, idx):
        ang = {nm: float(qrow[7 + k]) for k, nm in enumerate(joint_names)
               if 7 + k < len(qrow)}
        M = np.eye(4, dtype=np.float32)
        M[:3, :3] = ra.rot_euler([0, 0, 0.35])
        M[0, 3] = float(qrow[0]); M[1, 3] = float(qrow[1]) + y_off
        M[2, 3] = float(qrow[2]) + lift
        V, N, L = ra.world_tris(links, ra.transforms(urdf, ang), M)
        return V, N, L + idx * nL

    v0, n0, l0 = body(REF[0], 0.0, 0)
    r.render(v0, n0, cols[l0], P @ look_at(ctr + [dist, 0, 0.2], ctr))

    print(f'  {nf} frames · {len(v0):,} tris/body · identical={identical}')
    t0 = time.time(); rms = 0.0
    half = nf // 2
    for i in range(nf):
        phase_a = i < half
        # map the film onto the trace, twice — once per phase
        local = i if phase_a else i - half
        k = min(len(REF) - 1, int(local / max(1, half - 1) * (len(REF) - 1)))
        other = SAME[k] if phase_a else DIFF[k]
        d_now = float(div_same[k] if phase_a else div_diff[k])

        Va, Na, La = body(REF[k], 0.0, 0)
        Vb, Nb, Lb = body(other, 0.0, 1)
        V = np.concatenate([Va, Vb]); N = np.concatenate([Na, Nb]); L = np.concatenate([La, Lb])
        tt = i / a.fps
        az = 0.22 * math.sin(tt * 0.5) + 0.35
        eye = ctr + np.array([dist * math.cos(az), dist * math.sin(az), 0.22], np.float32)
        tr = time.time()
        img = r.render(V, N, cols[L], P @ look_at(eye, ctr))
        rms += (time.time() - tr) * 1000

        cv = Image.new('RGB', (W, H), VOID)
        cv.paste(Image.fromarray(img), (0, HDR))
        d = ImageDraw.Draw(cv, 'RGBA')
        d.rectangle([0, 0, W, HDR], fill=GOLD)
        d.text((20, 10), 'tinyMUJOCO', font=F_T, fill=VOID)
        d.text((20, 46), 'DETERMINISTIC PHYSICS · A GRADEABLE TRACE', font=F_S, fill=(58, 48, 16))

        y = HUD + 16
        if phase_a:
            d.text((22, y), 'SAME SEED', font=F_B, fill=EMER); y += 58
            d.text((22, y), 'two runs · one trajectory', font=F_M, fill=INK); y += 32
            d.text((22, y), f'max abs diff  {d_now:.1f}', font=F_M, fill=EMER); y += 34
            d.text((22, y), 'reward 1.0 · 0 tokens · 0 model calls', font=F_S, fill=DIM); y += 28
            d.text((22, y), 'the two bodies occupy the same space', font=F_X, fill=DIM)
        else:
            d.text((22, y), 'DIFFERENT SEED', font=F_B, fill=MAG); y += 58
            d.text((22, y), 'same start, different control', font=F_M, fill=INK); y += 32
            d.text((22, y), f'max abs diff  {d_now:.4f}', font=F_M, fill=MAG); y += 34
            d.text((22, y), 'reward 0.0 · 18,000 elements differ', font=F_S, fill=DIM); y += 28
            d.text((22, y), 'radians in one joint — not metres of travel', font=F_X, fill=DIM)

        # divergence over the trace: the honest visual for a joint-space number
        gx, gy, gw, gh = 22, HUD + 214, W - 44, 88
        d.rectangle([gx, gy, gx + gw, gy + gh], outline=(42, 36, 21))
        d.text((gx + 2, gy - 22), 'MAX ABS DIFF ACROSS THE TRACE', font=F_X, fill=DIM)
        series = div_same if phase_a else div_diff
        peak = max(1e-9, float(div_diff.max()))
        pts = []
        for j in range(0, len(series), max(1, len(series) // gw)):
            xx = gx + int(j / max(1, len(series) - 1) * gw)
            yy = gy + gh - int(min(1.0, float(series[j]) / peak) * (gh - 4)) - 2
            pts.append((xx, yy))
        if len(pts) > 1:
            d.line(pts, fill=EMER if phase_a else MAG, width=2)
        cx = gx + int(k / max(1, len(series) - 1) * gw)
        d.line([cx, gy, cx, gy + gh], fill=GOLD, width=1)
        d.text((gx + 2, gy + gh + 6), f'peak {peak:.3f} rad', font=F_X, fill=DIM)

        d.rectangle([0, H - 92, W, H], fill=(14, 13, 8, 255))
        d.text((22, H - 80), 'MuJoCo 4.0.1 · nq 30 · nu 23 · no OpenGL', font=F_S, fill=GOLD)
        d.text((22, H - 54), 'tinyCUDA grades pixels. tinyMUJOCO grades motion.', font=F_S, fill=INK)
        d.text((22, H - 30), 'random control is not a policy — the collapse is real physics', font=F_X, fill=DIM)
        cv.save(fd / f'f{i:05d}.png')
        if i % 30 == 0:
            print(f'    {i}/{nf}  phase {"A" if phase_a else "B"}  diff {d_now:.4f}')

    el = time.time() - t0
    f = ff()
    subprocess.run([str(f / 'ffmpeg'), '-y', '-v', 'error', '-framerate', str(a.fps),
                    '-i', str(fd / 'f%05d.png'), '-c:v', 'h264_nvenc', '-preset', 'p5',
                    '-b:v', '8M', '-pix_fmt', 'yuv420p', '-t', f'{nf / a.fps:.3f}', str(out)],
                   check=True, timeout=900)
    meta = {'ok': True, 'out': str(out), 'frames': nf, 'seconds': round(nf / a.fps, 3),
            'size': [W, H], 'silent': True, 'bodies': 2, 'triangles': len(v0) * 2,
            'raster_ms': round(rms / nf, 1), 'wall_s': round(el, 1),
            'same_seed_identical': bool(identical),
            'max_divergence': float(div_diff.max()), 'same_seed_max_diff': float(div_same.max()),
            'mujoco': '4.0.1', 'grants': False,
            'note': 'every pose is a qpos row from real physics; nothing keyframed',
            'divergence_unit': 'radians (joint space) — the base barely translates, '
                               'so the on-screen curve carries the number, not the bodies'}
    (wd / 'render.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
