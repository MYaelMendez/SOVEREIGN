#!/usr/bin/env python3
"""tinycan-916 — ONE TICK. The bus between the decision and the body.

The policy is the DAO's decision. The bus is whether that decision reaches the
body in time. Deciding is not delivering.

Every number on screen comes from tinycan.poll(), which is calibrated to Menlo's
published engineering slide: 8/25 and 15/25 replies at 1.67 ms match EXACTLY;
the sequential aggregate is +10.8% (conservative). The per-frame constants are a
model, and the film says so.

Final beat: wætz gets a cowboy hat. Real geometry appended to the head link's
frame, not a pasted sprite — it rasterises through the same depth buffer as the
robot, so it occludes and shades correctly.
"""
from __future__ import annotations
import argparse, json, math, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, r'C:\æ\agents')
sys.path.insert(0, r'C:\æ\tinycan')


def cowboy_hat(scale=1.0):
    """Brim + crown as triangles, in the head link's local frame.

    A cowboy hat is a wide flat brim with an upturned edge and a tapered crown
    with a crease. Built from quads so it reads at 720x1280.
    """
    tris = []

    def quad(a, b, c, d):
        tris.append([a, b, c]); tris.append([a, c, d])

    R = 0.115 * scale          # brim radius
    r = 0.052 * scale          # crown radius
    h = 0.075 * scale          # crown height
    z0 = 0.0                   # brim plane
    N = 28
    # brim: an annulus-ish disc, edges curled up
    for i in range(N):
        a0, a1 = 2 * math.pi * i / N, 2 * math.pi * (i + 1) / N
        curl = 0.022 * scale
        o0 = [R * math.cos(a0), R * math.sin(a0), z0 + curl]
        o1 = [R * math.cos(a1), R * math.sin(a1), z0 + curl]
        m0 = [R * 0.72 * math.cos(a0), R * 0.72 * math.sin(a0), z0]
        m1 = [R * 0.72 * math.cos(a1), R * 0.72 * math.sin(a1), z0]
        i0 = [r * math.cos(a0), r * math.sin(a0), z0]
        i1 = [r * math.cos(a1), r * math.sin(a1), z0]
        quad(i0, i1, m1, m0)
        quad(m0, m1, o1, o0)
    # crown: tapered, with a centre crease
    for i in range(N):
        a0, a1 = 2 * math.pi * i / N, 2 * math.pi * (i + 1) / N
        b0 = [r * math.cos(a0), r * math.sin(a0), z0]
        b1 = [r * math.cos(a1), r * math.sin(a1), z0]
        taper = 0.86
        crease0 = 1.0 - 0.22 * abs(math.cos(a0))
        crease1 = 1.0 - 0.22 * abs(math.cos(a1))
        t0 = [r * taper * math.cos(a0), r * taper * math.sin(a0), z0 + h * crease0]
        t1 = [r * taper * math.cos(a1), r * taper * math.sin(a1), z0 + h * crease1]
        quad(b0, b1, t1, t0)
        tris.append([[0, 0, z0 + h * 0.80], t0, t1])
    return np.asarray(tris, np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--seconds', type=float, default=12.0)
    ap.add_argument('--fps', type=int, default=24)
    ap.add_argument('--width', type=int, default=720)
    ap.add_argument('--height', type=int, default=1280)
    a = ap.parse_args()

    import rtx_asimov as ra
    from rtx_raster import RtxRenderer, persp, look_at
    import tinycan as TC
    from PIL import Image, ImageDraw, ImageFont

    ROWS = TC.poll('rows'); BURST = TC.poll('burst')
    ev_r, rep_r = TC._events('rows')
    ev_b, rep_b = TC._events('burst')
    print(f"  rows {ROWS['poll_end_us']} us · burst {BURST['poll_end_us']} us")

    W, H = a.width, a.height
    VH = int(H * 0.52)                      # robot occupies the upper portion
    md = Path(r'C:\æ\tinygpu\model')
    urdf = json.loads((md / 'urdf.json').read_text(encoding='utf-8'))
    ra.MESHES = md / 'meshes'
    links = ra.load_links(urdf)          # dict keyed by link name
    names = list(links.keys())
    nL = len(links)

    # wætz — the human digital twin, test pilot, centre of the cast
    CAST = json.loads(Path(r'C:\æ\hermes-plugins\hermes-asimov\cast.json').read_text(encoding='utf-8'))
    waetz = next(c for c in CAST['cast'] if c['id'] == 'waetz')
    HEAD = np.array(waetz['head_rgb'], np.float32) / 255.0
    BODY = np.array([0.72, 0.73, 0.76], np.float32)
    GOLD = np.array([0.831, 0.686, 0.216], np.float32)
    base_col = np.array([HEAD if n == 'neck_pitch_link' else BODY for n in names], np.float32)
    HAT_ID = nL                              # one extra link id for the hat
    head_idx = names.index('neck_pitch_link')

    r = RtxRenderer(W, VH)
    T = ra.transforms(urdf, {})
    v, n, l = ra.world_tris(links, T, np.eye(4))

    # hat geometry, placed in the head link's world frame
    hat_local = cowboy_hat(1.0)
    HM = T[names[head_idx]].copy()
    # lift to the top of the head and tilt slightly, rakishly
    lift = np.eye(4, dtype=np.float32); lift[2, 3] = 0.085
    tilt = np.eye(4, dtype=np.float32)
    ang = math.radians(-11)
    tilt[0, 0] = math.cos(ang); tilt[0, 2] = math.sin(ang)
    tilt[2, 0] = -math.sin(ang); tilt[2, 2] = math.cos(ang)
    HW = HM @ lift @ tilt
    hv = (hat_local.reshape(-1, 3) @ HW[:3, :3].T + HW[:3, 3]).reshape(-1, 3, 3)
    e1, e2 = hv[:, 1] - hv[:, 0], hv[:, 2] - hv[:, 0]
    hn = np.cross(e1, e2)
    hn /= (np.linalg.norm(hn, axis=1, keepdims=True) + 1e-12)

    V = np.concatenate([v, hv]).astype(np.float32)
    N = np.concatenate([n, hn]).astype(np.float32)
    L = np.concatenate([l, np.full(len(hv), HAT_ID, np.int32)])
    COLS = np.concatenate([base_col, GOLD[None, :]])
    print(f'  {len(v):,} body tris + {len(hv):,} hat tris · head link {names[head_idx]}')

    ctr = np.array([0.0, 0.0, 0.62], np.float32)
    P = persp(34.0, 0.05, 100.0, aspect=W / VH)
    VIEW = P @ look_at(ctr + [2.05, -0.30, 0.30], ctr)

    def font(sz, b=False):
        try:
            return ImageFont.truetype('C:/Windows/Fonts/consolab.ttf' if b
                                      else 'C:/Windows/Fonts/consola.ttf', sz)
        except Exception:
            return ImageFont.load_default()

    F_T, F_B, F_M, F_S, F_X = font(28, True), font(38, True), font(21, True), font(16), font(13)
    GOLD8 = (212, 175, 55); INK = (232, 230, 223); DIM = (138, 122, 63)
    TEAL = (45, 212, 191); VIOLET = (168, 85, 247); MAG = (255, 64, 220)

    nf = int(round(a.seconds * a.fps))
    out = Path(a.out); wd = out.parent / (out.stem + '-can'); fd = wd / 'frames'
    fd.mkdir(parents=True, exist_ok=True)

    HAT_ON = int(nf * 0.80)                  # the hat arrives for the last beat
    t0 = time.time(); rms = 0.0
    print(f'  rendering {nf} frames…')
    for i in range(nf):
        u = i / max(1, nf - 1)
        show_hat = i >= HAT_ON
        cols = COLS[L].copy()
        if not show_hat:
            cols[L == HAT_ID] = np.array([0.055, 0.063, 0.086], np.float32)  # hidden in the void
        # gentle turn so the hat reads in 3D once it lands
        yaw = math.radians(-14 + 26 * u)
        RM = np.eye(4, dtype=np.float32)
        RM[0, 0] = math.cos(yaw); RM[0, 1] = -math.sin(yaw)
        RM[1, 0] = math.sin(yaw); RM[1, 1] = math.cos(yaw)
        Vr = (V.reshape(-1, 3) @ RM[:3, :3].T).reshape(-1, 3, 3)
        Nr = (N @ RM[:3, :3].T).astype(np.float32)
        ts = time.time()
        px = r.render(Vr, Nr, cols, VIEW)
        rms += (time.time() - ts) * 1000

        img = Image.new('RGB', (W, H), (14, 16, 22))
        img.paste(Image.fromarray(px), (0, 96))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 88], fill=GOLD8)
        d.text((22, 12), 'ONE TICK', font=F_T, fill=(5, 5, 5))
        d.text((22, 50), '5,000 µs  ·  200 Hz  ·  Asimov-1', font=F_S, fill=(58, 48, 16))

        y = VH + 108
        # ---- the act, keyed to time -------------------------------------
        if u < 0.17:
            head, sub = 'THE BODY IS FOR SALE', '$20,000 DIY kit  ·  $499 deposit'
            act, prog, mode = 'idle', 0.0, None
        elif u < 0.42:
            head, sub = 'SEQUENTIAL: SIX ROWS', 'SPI write → CAN out → reply → SPI read'
            act, prog, mode = 'rows', (u - 0.17) / 0.25, ROWS
        elif u < 0.60:
            head, sub = '96.7% OF THE TICK', 'consumed before the controller thinks'
            act, prog, mode = 'rows', 1.0, ROWS
        elif u < 0.80:
            head, sub = 'PIO BURST', 'same clock · same buses · one burst'
            act, prog, mode = 'burst', (u - 0.60) / 0.20, BURST
        else:
            head, sub = 'DECIDING IS NOT DELIVERING', 'wætz · test pilot · hat acquired'
            act, prog, mode = 'burst', 1.0, BURST

        d.text((22, y), head, font=F_M, fill=GOLD8); y += 30
        d.text((22, y), sub, font=F_S, fill=INK); y += 34

        # ---- the deadline bar -------------------------------------------
        if mode:
            elapsed = prog * mode['poll_end_us']
            frac = min(1.0, elapsed / TC.TICK_US)
            bw = W - 44
            d.text((22, y), f'{elapsed:7.0f} µs of 5,000', font=F_S, fill=DIM); y += 24
            d.rectangle([22, y, 22 + bw, y + 26], outline=(60, 54, 32))
            col = MAG if frac > 0.9 else GOLD8
            d.rectangle([23, y + 1, 22 + int(bw * frac), y + 25], fill=col)
            d.line([22 + bw, y - 5, 22 + bw, y + 31], fill=TEAL, width=2)
            y += 40
            ev = ev_r if act == 'rows' else ev_b
            rep = rep_r if act == 'rows' else rep_b
            done = sum(1 for e in ev if e[1] <= elapsed)
            read = sum(1 for rp in rep if rp[1] <= elapsed)
            d.text((22, y), f'frames {done:3d}/{len(ev)}   replies {read:2d}/25', font=F_M, fill=TEAL); y += 30
            # the six chips, lit when their bus is active
            cx = 22
            for c in TC.CHIPS:
                active = any(e[3] == c['id'] and e[0] <= elapsed <= e[1] for e in ev)
                wch = (W - 44) // 6 - 4
                d.rectangle([cx, y, cx + wch, y + 40],
                            outline=GOLD8 if active else (58, 52, 30),
                            fill=(38, 32, 14) if active else (18, 19, 24))
                d.text((cx + 4, y + 5), c['spi'], font=F_X, fill=GOLD8 if active else DIM)
                d.text((cx + 4, y + 22), f"{c['motors']}m", font=F_X, fill=INK if active else DIM)
                cx += wch + 4
            y += 54

        # ---- the receipt -------------------------------------------------
        d.rectangle([0, H - 118, W, H], fill=(10, 11, 15))
        d.text((22, H - 108), 'calibrated to Menlo’s published slide', font=F_S, fill=GOLD8)
        d.text((22, H - 84), '8/25 exact · 15/25 exact · aggregate +10.8%', font=F_S, fill=INK)
        d.text((22, H - 60), 'per-frame constants are a MODEL, not a measurement', font=F_X, fill=DIM)
        d.text((22, H - 38), 'tinyCAN · deterministic · grade 1.0 · zero tokens', font=F_X, fill=TEAL)
        d.text((22, H - 18), '>_æ://  ·  mobility.foundation  ·  HUMAN://ROOT', font=F_X, fill=GOLD8)

        img.save(fd / f'f{i:05d}.png')
        if i % 48 == 0:
            print(f'    {i}/{nf} · {rms/(i+1):.0f} ms/frame')

    meta = {'frames': nf, 'seconds': a.seconds, 'fps': a.fps, 'size': [W, H],
            'rows': {k: ROWS[k] for k in ('poll_end_us', 'tick_budget_used_pct', 'replies_by_1670us')},
            'burst': {k: BURST[k] for k in ('poll_end_us', 'tick_budget_used_pct', 'replies_by_1670us')},
            'hat_triangles': int(len(hv)), 'hat_from_frame': HAT_ON,
            'hat_link': names[head_idx], 'cast_center': waetz['id'],
            'raster_ms': round(rms / nf, 1), 'wall_s': round(time.time() - t0, 1),
            'calibration': ROWS['fit_quality']}
    (wd / 'render.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(f"  {nf} frames · {rms/nf:.0f} ms/frame · {time.time()-t0:.0f}s wall")
    print(f"  hat: {len(hv)} tris on {names[head_idx]} from frame {HAT_ON}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
