"""
agentic_ontology_gif.py — animated 9:16 GIF of the agentic ontology.

Deterministic: every frame is drawn from brain_index.py's real taxonomy, same
palette and layout as agentic_ontology_still.py. The only animation is a pulse
traveling around the nine category nodes and the five OSW stages — no invented
data, no generative model.

Output: agentic_ontology.gif (576x1024, looping).
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 576, 1024
FRAMES = 60          # one full cycle around 9 nodes + 5 stages
VOID = (5, 5, 5)
GOLD = (212, 175, 55)
GOLD2 = (240, 212, 135)
EMERALD = (0, 255, 157)
CYAN = (0, 234, 255)
VIOLET = (140, 114, 255)
RED = (255, 77, 95)
INK = (232, 230, 223)
MUTED = (111, 106, 92)
LINE = (60, 50, 22)

CATS = [
    ("CHASSIS",   "⌘", "language / runtime",  CYAN),
    ("AGENT",     "◈", "human loop / fleet",  GOLD2),
    ("COMPUTE",   "▤", "GPU / CUDA / RTX",    VIOLET),
    ("MEDIA",     "▶", "video / proof",       EMERALD),
    ("CUSTODY",   "▣", "vault / authority",   RED),
    ("ECONOMY",   "$", "DAO / rails",         GOLD),
    ("KNOWLEDGE", "✎", "curricula / teaching", INK),
    ("INFRA",     "⬡", "mesh / deploy",       CYAN),
    ("SURFACE",   "□", "entry / index",       MUTED),
]
OSW = ["DISCOVER", "FORK", "CONNECT", "ORCHESTRATE", "VERIFY"]


def font(sz: int, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for p in (Path("C:/Windows/Fonts") / name,
              Path("C:/Users/yaelm/AppData/Local/hermes/cache/scratch") / name):
        if p.exists():
            return ImageFont.truetype(str(p), sz)
    return ImageFont.load_default()


def pulse(phase: float, i: int, n: int) -> float:
    """0..1 highlight as a traveling wave visits node i."""
    d = (phase * n - i) % n
    return max(0.0, 1.0 - d)


def dtext(d, xy, s, f, fill, anchor="la"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def frame(k: int, total: int) -> Image.Image:
    img = Image.new("RGB", (W, H), VOID)
    d = ImageDraw.Draw(img)
    phase = k / total  # 0..1 over the full loop

    f_eyebrow = font(15); f_head = font(34, True); f_sub = font(15)
    f_cat = font(17, True); f_glyph = font(26, True); f_role = font(12)
    f_ae = font(96, True); f_rail = font(12, True); f_foot = font(11)

    dtext(d, (28, 38), "#OPENSOURCEWARE · AGENTIC ENGINEERING", f_eyebrow, GOLD)
    dtext(d, (28, 70), "AGENTIC ONTOLOGY", f_head, INK)
    dtext(d, (28, 118), "nine categories · one pivot · the human loop", f_sub, MUTED)
    d.line([(28, 146), (W - 28, 146)], fill=LINE, width=1)

    cx, cy, R = W // 2, 440, 178
    d.ellipse([cx - R - 18, cy - R - 18, cx + R + 18, cy + R + 18],
              outline=(46, 40, 20), width=1)
    n = len(CATS)
    for i, (name, glyph, role, col) in enumerate(CATS):
        ang = -math.pi / 2 + i * (2 * math.pi / n)
        nx, ny = math.cos(ang), math.sin(ang)
        px, py = cx + nx * R, cy + ny * R
        p = pulse(phase, i, n)
        lit = tuple(min(255, int(c * (0.55 + 0.45 * p))) for c in col)
        d.line([(cx + nx * 60, cy + ny * 60), (cx + nx * (R - 30), cy + ny * (R - 30))],
               fill=(lit[0] // 4 + 20, lit[1] // 4 + 20, lit[2] // 4 + 10),
               width=2 + int(2 * p))
        rr = 24 + int(4 * p)
        d.ellipse([px - rr, py - rr, px + rr, py + rr], outline=lit, width=2)
        d.ellipse([px - 19, py - 19, px + 19, py + 19],
                  fill=(lit[0] // 12, lit[1] // 12, lit[2] // 12))
        dtext(d, (px, py), glyph, f_glyph, lit, anchor="mm")
        lx, ly = px + nx * 40, py + ny * 40
        dtext(d, (lx, ly), name, f_cat, lit, anchor="mm")
        dtext(d, (lx, ly + 15), role, f_role, MUTED, anchor="mm")

    d.ellipse([cx - 54, cy - 54, cx + 54, cy + 54], outline=GOLD, width=2)
    d.ellipse([cx - 46, cy - 46, cx + 46, cy + 46], fill=(18, 14, 4))
    dtext(d, (cx, cy - 6), "æ", f_ae, GOLD, anchor="mm")
    dtext(d, (cx, cy + 46), "THE HUMAN LOOP", font(11, True), GOLD2, anchor="mm")

    d.line([(28, 682), (W - 28, 682)], fill=LINE, width=1)
    dtext(d, (28, 694), "#OPENSORCEWARE CYCLE", f_eyebrow, GOLD)
    y = 738
    seg = (W - 56) // len(OSW)
    op = pulse(phase, 0, len(OSW))
    for i, word in enumerate(OSW):
        x = 28 + i * seg
        col = EMERALD if i == len(OSW) - 1 else (GOLD2 if i % 2 == 0 else CYAN)
        p = pulse(phase, i, len(OSW))
        lit = tuple(min(255, int(c * (0.6 + 0.4 * p))) for c in col)
        d.rounded_rectangle([x, y, x + seg - 8, y + 42], radius=6,
                            outline=lit, width=2 if p > 0.5 else 1,
                            fill=(lit[0] // 16, lit[1] // 16, lit[2] // 16))
        dtext(d, (x + (seg - 8) / 2, y + 21), word, f_rail, lit, anchor="mm")
        if i < len(OSW) - 1:
            dtext(d, (x + seg - 4, y + 21), "›", font(16, True), MUTED, anchor="mm")

    d.line([(28, 812), (W - 28, 812)], fill=LINE, width=1)
    dtext(d, (28, 826), "CLASSIFICATION SOURCE", f_eyebrow, GOLD)
    dtext(d, (28, 848), "mp4-factory/brain_index.py · ONTOLOGY + CATEGORY_META", f_foot, INK)
    dtext(d, (28, 868), "9 categories · first-match keyword rule · live site index", f_foot, MUTED)
    dtext(d, (28, 900), "PROVEN  taxonomy in running index", f_foot, EMERALD)
    dtext(d, (28, 920), "BUILT   this still, rendered deterministically from that taxonomy", f_foot, GOLD2)
    dtext(d, (28, 940), "LIABILITY  counts not pulled live; structure, not volume", f_foot, RED)
    dtext(d, (28, 985), "576×1024 · #050505 · #D4AF37 · #00ff9d", f_foot, MUTED)
    return img


def main():
    frames = [frame(k, FRAMES) for k in range(FRAMES)]
    out = Path(__file__).parent / "agentic_ontology.gif"
    frames[0].save(
        out, save_all=True, append_images=frames[1:],
        duration=90, loop=0, optimize=False, disposal=2,
    )
    print(f"wrote {out} ({len(frames)} frames, {out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
