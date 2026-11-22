"""
agentic_ontology_still.py — deterministic 9:16 still of the agentic ontology.

Data source: brain_index.py ONTOLOGY + CATEGORY_META (the site's real taxonomy).
Rendered with PIL, not a generative model — no invented numbers, no stray glyphs.
Output: agentic_ontology_9x16.png (576x1024, ratio 0.5625).
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 576, 1024
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

# The nine real categories, with glyphs from CATEGORY_META.
# ring radius order = angle around center; color by authority/function band.
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
    # DejaVuSans ships with the Python/PIL distro on this host.
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for p in (
        Path("C:/Windows/Fonts") / ("dejavu-sans-bold.ttf" if bold else "dejavu-sans.ttf"),
        Path("C:/Windows/Fonts") / name,
        Path("C:/Users/yaelm/AppData/Local/hermes/cache/scratch") / name,
    ):
        if p.exists():
            return ImageFont.truetype(str(p), sz)
    return ImageFont.load_default()


def dtext(d, xy, s, f, fill, anchor="la"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def main():
    base = Image.new("RGB", (W, H), VOID)
    d = ImageDraw.Draw(base)

    # subtle vignette glow behind the graph
    for i in range(60, 0, -1):
        a = int((60 - i) / 60 * 6)
        d.ellipse([W // 2 - i * 5, 430 - i * 5, W // 2 + i * 5, 430 + i * 5],
                  outline=(a, a, int(a * 0.5)))

    f_eyebrow = font(15)
    f_head = font(34, True)
    f_sub = font(15)
    f_cat = font(17, True)
    f_glyph = font(26, True)
    f_role = font(12)
    f_ae = font(96, True)
    f_rail = font(12, True)
    f_foot = font(11)

    # header
    dtext(d, (28, 38), "#OPENSOURCEWARE · AGENTIC ENGINEERING", f_eyebrow, GOLD)
    dtext(d, (28, 70), "AGENTIC ONTOLOGY", f_head, INK)
    dtext(d, (28, 118), "nine categories · one pivot · the human loop", f_sub, MUTED)
    d.line([(28, 146), (W - 28, 146)], fill=LINE, width=1)

    # radial ontology graph centered at (288, 430), radius 175
    cx, cy, R = W // 2, 440, 178
    d.ellipse([cx - R - 18, cy - R - 18, cx + R + 18, cy + R + 18],
              outline=(46, 40, 20), width=1)
    n = len(CATS)
    for i, (name, glyph, role, col) in enumerate(CATS):
        ang = -math.pi / 2 + i * (2 * math.pi / n)
        nx, ny = math.cos(ang), math.sin(ang)
        # node position
        px, py = cx + nx * R, cy + ny * R
        # spoke
        d.line([(cx + nx * 60, cy + ny * 60), (cx + nx * (R - 30), cy + ny * (R - 30))],
               fill=(col[0] // 4 + 20, col[1] // 4 + 20, col[2] // 4 + 10), width=2)
        # node ring
        d.ellipse([px - 24, py - 24, px + 24, py + 24], outline=col, width=2)
        d.ellipse([px - 19, py - 19, px + 19, py + 19], fill=(col[0] // 12, col[1] // 12, col[2] // 12))
        dtext(d, (px, py), glyph, f_glyph, col, anchor="mm")
        # label just outside node
        lx = px + nx * 40
        ly = py + ny * 40
        anchor = "mm"
        dtext(d, (lx, ly), name, f_cat, col, anchor=anchor)
        dtext(d, (lx, ly + 15), role, f_role, MUTED, anchor="mm")

    # central pivot
    d.ellipse([cx - 54, cy - 54, cx + 54, cy + 54], outline=GOLD, width=2)
    d.ellipse([cx - 46, cy - 46, cx + 46, cy + 46], fill=(18, 14, 4))
    dtext(d, (cx, cy - 6), "æ", f_ae, GOLD, anchor="mm")
    dtext(d, (cx, cy + 46), "THE HUMAN LOOP", font(11, True), GOLD2, anchor="mm")

    # OSW arc rail
    d.line([(28, 682), (W - 28, 682)], fill=LINE, width=1)
    dtext(d, (28, 694), "#OPENSORCEWARE CYCLE", f_eyebrow, GOLD)
    y = 738
    seg = (W - 56) // len(OSW)
    for i, word in enumerate(OSW):
        x = 28 + i * seg
        col = EMERALD if i == len(OSW) - 1 else (GOLD2 if i % 2 == 0 else CYAN)
        d.rounded_rectangle([x, y, x + seg - 8, y + 42], radius=6,
                            outline=col, width=1, fill=(col[0] // 16, col[1] // 16, col[2] // 16))
        dtext(d, (x + (seg - 8) / 2, y + 21), word, f_rail, col, anchor="mm")
        if i < len(OSW) - 1:
            dtext(d, (x + seg - 4, y + 21), "›", font(16, True), MUTED, anchor="mm")

    # footer — PROVEN / BUILT honesty line, from brain_index.py (measured source)
    d.line([(28, 812), (W - 28, 812)], fill=LINE, width=1)
    dtext(d, (28, 826), "CLASSIFICATION SOURCE", f_eyebrow, GOLD)
    dtext(d, (28, 848), "mp4-factory/brain_index.py · ONTOLOGY + CATEGORY_META", f_foot, INK)
    dtext(d, (28, 868), "9 categories · first-match keyword rule · live site index", f_foot, MUTED)
    dtext(d, (28, 900), "PROVEN  taxonomy in running index", f_foot, EMERALD)
    dtext(d, (28, 920), "BUILT   this still, rendered deterministically from that taxonomy", f_foot, GOLD2)
    dtext(d, (28, 940), "LIABILITY  counts not pulled live; structure, not volume", f_foot, RED)
    dtext(d, (28, 985), "576×1024 · #050505 · #D4AF37 · #00ff9d", f_foot, MUTED)

    out = Path(__file__).parent / "agentic_ontology_9x16.png"
    base.save(out)
    print(f"wrote {out} ({W}x{H}, ratio {W/H:.4f})")


if __name__ == "__main__":
    main()
