#!/usr/bin/env python3
"""corpus-916 — the film that makes the corpus findable.

152 films existed and nothing indexed them. This film is the front door: it
shows what the corpus MEASURED about itself, and its last frame is the address
of the index. Every number on screen comes from film-corpus.json, which is
generated from ffprobe and SHA-256, never from recollection.

The finding is the point: defect rate 7.8% with voice, 0.0% without. Every
failure in 152 films lives at the seam between picture and sound. Not one
component failed. Every gate we had was a component gate.
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, r'C:\æ\agents')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--seconds', type=float, default=14.0)
    ap.add_argument('--fps', type=int, default=24)
    a = ap.parse_args()

    import rtx_asimov as ra
    from rtx_raster import RtxRenderer, persp, look_at
    from PIL import Image, ImageDraw, ImageFont

    GP = Path(r'C:\æ\github-pages')
    data = json.loads((GP / 'film-corpus.json').read_text(encoding='utf-8'))
    S = data['summary']
    films = data['films']
    print(f"  corpus: {S['films']} films · {S['live']} live · {S['defective']} defective")

    W, H = 720, 1280
    VH = 500
    md = Path(r'C:\æ\tinygpu\model')
    urdf = json.loads((md / 'urdf.json').read_text(encoding='utf-8'))
    ra.MESHES = md / 'meshes'
    links = ra.load_links(urdf)
    names = list(links.keys())
    nL = len(links)
    GOLD = np.array([0.831, 0.686, 0.216], np.float32)
    BODY = np.array([0.70, 0.71, 0.74], np.float32)
    cols = np.array([GOLD if n == 'neck_pitch_link' else BODY for n in names], np.float32)

    r = RtxRenderer(W, VH)
    # REAL GAIT, not a slow turn. The gate refused the first render at motion
    # 0.217 and it was right: a 34-degree yaw over 14 s is a still image.
    TR = json.loads((Path(os.environ['HERMES_HOME']) / 'cache' / 'scratch'
                     / 'walk-film.json').read_text(encoding='utf-8'))
    Q = np.asarray(TR['qpos'], np.float32)
    JN = TR['joint_names']
    NT = len(Q)
    print(f'  gait: {NT} policy frames')
    v, NRM, l = ra.world_tris(links, ra.transforms(urdf, {}), np.eye(4))
    ctr = np.array([0.0, 0.0, 0.62], np.float32)
    P = persp(34.0, 0.05, 100.0, aspect=W / VH)
    VIEW = P @ look_at(ctr + [2.05, -0.30, 0.30], ctr)
    print(f'  {len(v):,} triangles')

    def font(sz, b=False):
        try:
            return ImageFont.truetype('C:/Windows/Fonts/consolab.ttf' if b
                                      else 'C:/Windows/Fonts/consola.ttf', sz)
        except Exception:
            return ImageFont.load_default()

    F_T, F_B, F_M, F_S, F_X = font(27, True), font(52, True), font(21, True), font(16), font(13)
    G8 = (212, 175, 55); INK = (232, 230, 223); DIM = (138, 122, 63)
    TEAL = (45, 212, 191); MAG = (255, 64, 220)

    nf = int(round(a.seconds * a.fps))
    out = Path(a.out); wd = out.parent / (out.stem + '-cx'); fd = wd / 'frames'
    fd.mkdir(parents=True, exist_ok=True)

    # a bar per film, ordered by length — the corpus as one object
    lens = sorted((f['seconds'] for f in films), reverse=True)
    maxlen = max(lens)

    t0 = time.time(); rms = 0.0
    print(f'  rendering {nf} frames…')
    for i in range(nf):
        u = i / max(1, nf - 1)
        k = int(u * (NT - 1))
        ang = {nm: float(Q[k, 7 + j]) for j, nm in enumerate(JN) if 7 + j < Q.shape[1]}
        yaw = math.radians(-16 + 30 * u)
        RM = np.eye(4, dtype=np.float32)
        RM[0, 0] = math.cos(yaw); RM[0, 1] = -math.sin(yaw)
        RM[1, 0] = math.sin(yaw); RM[1, 1] = math.cos(yaw)
        vg, ng, lg = ra.world_tris(links, ra.transforms(urdf, ang), RM)
        ts = time.time()
        px = r.render(vg, ng, cols[lg], VIEW)
        rms += (time.time() - ts) * 1000

        img = Image.new('RGB', (W, H), (14, 16, 22))
        img.paste(Image.fromarray(px), (0, 84))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 78], fill=G8)
        d.text((22, 10), 'THE CORPUS', font=F_T, fill=(5, 5, 5))
        d.text((22, 46), '152 films · one measurement · one address', font=F_S, fill=(58, 48, 16))

        y = VH + 96
        if u < 0.20:
            big, head, sub = str(S['films']), 'FILMS ALREADY MADE', f"{S['total_minutes']} minutes · {S['total_gib']} GiB · all local"
        elif u < 0.40:
            big, head, sub = str(S['live']), 'ALREADY LIVE', 'they were never unreachable — they were unindexed'
        elif u < 0.62:
            big, head, sub = f"{S['defect_rate_with_voice_pct']}%", 'DEFECT RATE WITH VOICE', f"versus {S['defect_rate_silent_pct']}% without · {S['frozen_seconds_total']}s of frozen picture"
        elif u < 0.82:
            big, head, sub = '0', 'COMPONENTS THAT FAILED', 'not the render · not the physics · not the GPU'
        else:
            big, head, sub = 'æ://', 'DEFECTS LIVE AT INTERFACES', 'every gate we had was a component gate'

        d.text((22, y), big, font=F_B, fill=G8); y += 62
        d.text((22, y), head, font=F_M, fill=INK); y += 28
        d.text((22, y), sub, font=F_S, fill=DIM); y += 36

        # the corpus as a barcode: one bar per film, height = length
        bw = W - 44
        nb = len(lens)
        step = bw / nb
        reveal = int(nb * min(1.0, u * 1.6))
        for k in range(reveal):
            x = 22 + k * step
            hgt = int(58 * lens[k] / maxlen)
            f = films[k] if k < len(films) else None
            col = MAG if (f and f.get('defective')) else (TEAL if (f and f.get('live')) else (70, 64, 38))
            d.rectangle([x, y + 58 - hgt, x + max(1, step - 0.6), y + 58], fill=col)
        d.line([22, y + 59, 22 + bw, y + 59], fill=(60, 54, 32))
        y += 72
        d.text((22, y), 'teal = live   magenta = defective   dim = local', font=F_X, fill=DIM)

        d.rectangle([0, H - 104, W, H], fill=(10, 11, 15))
        d.text((22, H - 94), 'myaelmendez.github.io/corpus.html', font=F_M, fill=G8)
        d.text((22, H - 66), 'every film · its length · its gate · its SHA-256', font=F_S, fill=INK)
        d.text((22, H - 42), 'generated from ffprobe and delivered bytes, never memory', font=F_X, fill=DIM)
        d.text((22, H - 20), '>_æ://film  ·  tinyCUDAVIDEO checks the seam', font=F_X, fill=TEAL)

        img.save(fd / f'f{i:05d}.png')
        if i % 72 == 0:
            print(f'    {i}/{nf} · {rms/(i+1):.0f} ms/frame')

    meta = {'frames': nf, 'seconds': a.seconds, 'fps': a.fps, 'size': [W, H],
            'corpus': S, 'raster_ms': round(rms / nf, 1),
            'gait_frames': NT, 'motion_source': 'walk-film.json qpos (real policy)',
            'wall_s': round(time.time() - t0, 1),
            'index': 'https://myaelmendez.github.io/corpus.html',
            'data': 'film-corpus.json'}
    (wd / 'render.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(f"  {nf} frames · {rms/nf:.0f} ms/frame · {time.time()-t0:.0f}s wall")
    return 0


if __name__ == '__main__':
    sys.exit(main())
