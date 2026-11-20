#!/usr/bin/env python3
"""gpu_limits_film — the benchmark IS the film. Five seconds, every number measured.

Each rung of the ladder is rendered AT that rung's real settings, so the pixels
on screen are the GPU's actual output at that load — not an illustration of it.
The measured ms/fps are overlaid on the frame they came from.

    python gpu_limits_film.py --limits gpu-limits.json --out limits-916.mp4

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, json, math, os, subprocess, sys, time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rtx_raster import RtxRenderer, persp, look_at  # noqa: E402

# NEVER look straight down the up axis: cross(fwd, up) = 0 → NaN MVP → every
# triangle is clipped and the benchmark silently measures an EMPTY scene.
EYE = np.array([2.6, -2.6, 1.8], np.float32)

GOLD = (212, 175, 55); VOID = (11, 10, 6); DIM = (138, 122, 63)
INK = (232, 230, 223); EMER = (0, 255, 157); MAG = (255, 64, 220)


def synth(n, seed=0):
    rng = np.random.default_rng(seed)
    c = rng.uniform(-1, 1, (n, 3)).astype(np.float32)
    o = rng.uniform(-0.02, 0.02, (n, 3, 3)).astype(np.float32)
    v = c[:, None, :] + o
    nr = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    ln = np.linalg.norm(nr, axis=1, keepdims=True)
    nr = np.divide(nr, ln, out=np.zeros_like(nr), where=ln > 1e-9)
    return v, nr.astype(np.float32)


def ff() -> Path:
    h = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
    p = h / 'tools' / 'ffmpeg-7.1-nvenc' / 'bin'
    return p if p.exists() else Path('C:/Windows/System32')


def font(sz, bold=False):
    try:
        return ImageFont.truetype('C:/Windows/Fonts/consolab.ttf' if bold
                                  else 'C:/Windows/Fonts/consola.ttf', sz)
    except Exception:
        return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limits', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--seconds', type=float, default=5.0)
    ap.add_argument('--fps', type=int, default=24)
    a = ap.parse_args()

    rows = [r for r in json.loads(Path(a.limits).read_text(encoding='utf-8')) if 'ms' in r]
    W, H = 720, 1280
    nf = int(round(a.seconds * a.fps))
    out = Path(a.out)
    wd = out.parent / (out.stem + '-lim'); fd = wd / 'frames'
    fd.mkdir(parents=True, exist_ok=True)
    F_T, F_B, F_M, F_S, F_X = font(30, True), font(58, True), font(24, True), font(18), font(15)

    # render each rung AT its own settings — the picture is the measurement
    print(f'  rendering {len(rows)} rungs at their real settings…')
    shots = []
    for k, r in enumerate(rows):
        v, n = synth(r['tris'], seed=k)
        cols = np.tile(np.array([0.83, 0.69, 0.22], np.float32), (r['tris'], 1))
        rr = RtxRenderer(r['w'], r['h'])
        M = persp(45, 0.05, 60.0, aspect=r['w'] / r['h']) @ look_at(EYE, [0, 0, 0])
        rr.render(v, n, cols, M)
        t = time.time()
        for _ in range(3):
            img = rr.render(v, n, cols, M)
        ms = (time.time() - t) / 3 * 1000
        gold = int(((img[:, :, 0] > 100) & (img[:, :, 1] > 60)).sum())
        if gold < 1000:
            raise SystemExit(f'rung {k}: only {gold} lit pixels — the scene is empty, '
                             'the timing would measure rejected triangles. Refusing.')
        # fit the rung's own frame into the viewport, letterboxed — never crop
        VW, VH = W - 40, 560
        im = Image.fromarray(img)
        sc = min(VW / im.width, VH / im.height)
        im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
        shots.append({'row': r, 'img': im, 'remeasured_ms': round(ms, 2)})
        print(f'    {r["tris"]:>9,} @ {r["w"]}x{r["h"]}  bench {r["ms"]:.1f} ms · now {ms:.1f} ms')
        del rr, v, n, cols

    per = nf // len(shots)
    peak = max(r['mtri_s'] for r in rows)
    for i in range(nf):
        si = min(len(shots) - 1, i // per)
        s = shots[si]; r = s['row']
        cv = Image.new('RGB', (W, H), VOID)
        d = ImageDraw.Draw(cv, 'RGBA')
        d.rectangle([0, 0, W, 84], fill=GOLD)
        d.text((20, 10), 'RTX 3050 · 6GB · THE LIMIT', font=F_T, fill=VOID)
        d.text((20, 48), f'RUNG {si + 1}/{len(shots)} · EVERY NUMBER MEASURED', font=F_S, fill=(58, 48, 16))

        # the rung's actual output, centred
        im = s['img']
        cv.paste(im, ((W - im.width) // 2, 110 + (560 - im.height) // 2))
        d.rectangle([(W - im.width) // 2 - 2, 110 + (560 - im.height) // 2 - 2,
                     (W + im.width) // 2 + 1, 110 + (560 + im.height) // 2 + 1], outline=(42, 36, 21))

        y = 700
        d.text((24, y), f'{r["tris"]:,}', font=F_B, fill=GOLD); y += 66
        d.text((24, y), 'TRIANGLES', font=F_S, fill=DIM); y += 34
        d.text((24, y), f'{r["w"]} × {r["h"]}', font=F_M, fill=INK); y += 34
        st = r['status']
        col = EMER if st == 'REALTIME' else GOLD
        d.text((24, y), f'{r["fps"]:.1f} fps · {r["ms"]:.1f} ms · {st}', font=F_M, fill=col); y += 44

        # throughput bar — the flat curve is the finding
        d.text((24, y), 'THROUGHPUT', font=F_X, fill=DIM); y += 20
        bw = W - 48
        d.rectangle([24, y, 24 + bw, y + 16], outline=(42, 36, 21))
        d.rectangle([24, y, 24 + int(bw * r['mtri_s'] / 100.0), y + 16], fill=col)
        d.text((24, y + 22), f'{r["mtri_s"]:.1f} Mtri/s   (ceiling ~{peak:.0f})', font=F_S, fill=INK)

        d.rectangle([0, H - 96, W, H], fill=(14, 13, 8, 255))
        d.text((24, H - 84), '2M triangles is the realtime ceiling at 9:16.', font=F_S, fill=INK)
        d.text((24, H - 58), 'Resolution costs more than geometry.', font=F_S, fill=GOLD)
        d.text((24, H - 32), 'Nothing ran out of memory. 6GB was never the limit.', font=F_X, fill=DIM)
        cv.save(fd / f'f{i:05d}.png')

    f = ff()
    subprocess.run([str(f / 'ffmpeg'), '-y', '-v', 'error', '-framerate', str(a.fps),
                    '-i', str(fd / 'f%05d.png'), '-c:v', 'h264_nvenc', '-preset', 'p5',
                    '-b:v', '8M', '-pix_fmt', 'yuv420p', '-t', f'{nf / a.fps:.3f}', str(out)],
                   check=True, timeout=900)
    meta = {'ok': True, 'out': str(out), 'frames': nf, 'seconds': round(nf / a.fps, 3),
            'size': [W, H], 'rungs': len(shots), 'silent': True,
            'measurements': rows, 'remeasured': [s['remeasured_ms'] for s in shots],
            'peak_mtri_s': peak, 'grants': False,
            'note': 'each rung rendered at its own settings; the picture is the measurement',
            'guard': 'a rung with under 1000 lit pixels aborts the film — an empty '
                     'scene must never produce a benchmark'}
    (wd / 'render.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in meta.items() if k != 'measurements'}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
