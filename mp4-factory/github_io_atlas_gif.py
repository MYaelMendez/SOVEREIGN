"""
github_io_atlas_gif.py — animated 9:16 GIF of the myaelmendez.github.io atlas.

Data source: C:/æ/github-pages/ae-atlas.js (window.AE_ATLAS), parsed at runtime.
The animation sweeps the four authority layers (a=0..3) and then the x15 Asimov
lane — the exact "bind x15 into the origin atlas" move described in
origin/README.md. Every coordinate and label is read from the atlas; nothing
is invented. Same palette as the other sovereign GIFs.

Output: github_io_atlas.gif (576x1024, infinite loop).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 576, 1024
FRAMES = 72
ATLAS_JS = Path("C:/æ/github-pages/ae-atlas.js")
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

# verbatim from origin/index.html: AXNAME / AXCOL
AXNAME = ["public", "published", "operator", "custody"]
AXCOL = [GOLD, CYAN, EMERALD, VIOLET]


def font(sz: int, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for p in (Path("C:/Windows/Fonts") / name,
              Path("C:/Users/yaelm/AppData/Local/hermes/cache/scratch") / name):
        if p.exists():
            return ImageFont.truetype(str(p), sz)
    return ImageFont.load_default()


def load_atlas():
    txt = ATLAS_JS.read_text(encoding="utf-8")
    m = re.search(r"window\.AE_ATLAS\s*=\s*(\[.*\])\s*;", txt, re.S)
    data = json.loads(m.group(1))
    return data


def dtext(d, xy, s, f, fill, anchor="la"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def frame(k: int, total: int, atlas) -> Image.Image:
    img = Image.new("RGB", (W, H), VOID)
    d = ImageDraw.Draw(img)
    phase = k / total

    f_eyebrow = font(15); f_head = font(30, True); f_sub = font(14)
    f_small = font(11); f_tiny = font(10); f_stat = font(22, True)
    f_coord = font(13, True)

    dtext(d, (28, 34), "MYAELMENDEZ.GITHUB.IO · THE TRUTH SURFACE", f_eyebrow, GOLD)
    dtext(d, (28, 64), "THE ATLAS", f_head, INK)
    dtext(d, (28, 104), f"{len(atlas)} addresses · four authority layers · x15 bound in", f_sub, MUTED)
    d.line([(28, 132), (W - 28, 132)], fill=LINE, width=1)

    # Top stat boxes
    by_a = Counter(e["a"] for e in atlas)
    xs = sorted({e["x"] for e in atlas})
    x15_all = [e for e in atlas if e["x"] == 15]
    boxes = [("ADDRESSES", str(len(atlas)), GOLD2),
             ("LANES x", str(len(xs)), CYAN),
             ("x15 ASIMOV", str(len(x15_all)), EMERALD)]
    seg = (W - 56) // 3
    for i, (lab, val, col) in enumerate(boxes):
        x = 28 + i * seg
        d.rounded_rectangle([x, 146, x + seg - 8, 212], radius=6,
                            outline=col, width=1, fill=(col[0] // 18, col[1] // 18, col[2] // 18))
        dtext(d, (x + (seg - 8) / 2, 160), lab, f_tiny, MUTED, anchor="mm")
        dtext(d, (x + (seg - 8) / 2, 186), val, f_stat, col, anchor="mm")

    # continuous scan line — guarantees a distinct frame at every phase step
    scanx = int(28 + (W - 56) * phase)
    d.line([(scanx, 138), (scanx, 212)], fill=GOLD2, width=2)
    d.rounded_rectangle([28, 218, W - 28, 222], radius=2, outline=(30, 26, 14))
    d.rounded_rectangle([28, 218, 28 + int((W - 56) * phase), 222], radius=2, fill=GOLD2)

    # Authority layer sweep bars (a=0..3)
    dtext(d, (28, 228), "AUTHORITY AXIS  æ", f_eyebrow, GOLD)
    layer_y = 256
    for a in range(4):
        y = layer_y + a * 52
        lit = (phase * 8) % 1.0 > 0.5
        p = 1.0 if ((phase * 8) // 1) % 4 == a else 0.0
        col = AXCOL[a]
        amp = 0.45 + 0.55 * p
        c = tuple(min(255, int(v * amp)) for v in col)
        d.rounded_rectangle([28, y, W - 28, y + 44], radius=6,
                            outline=c, width=2 if p else 1,
                            fill=(c[0] // 20, c[1] // 20, c[2] // 20))
        dtext(d, (42, y + 22), f"æ{a}", f_coord, c, anchor="lm")
        dtext(d, (84, y + 22), AXNAME[a].upper(), font(15, True), c, anchor="lm")
        dtext(d, (W - 42, y + 22), f"{by_a.get(a, 0)} addresses", f_small, MUTED, anchor="rm")

        # address chips for this layer, packed as x:y coordinates
        ents = [e for e in atlas if e["a"] == a]
        chipx = 84
        chipy = y + 34
        shown = 0
        limit = W - (68 if len(ents) > 10 else 36)
        for e in ents:
            lab = f"x{e['x']}:y{e['y']}"
            tw = d.textlength(lab, font=f_tiny) + 8
            if chipx + tw > limit:
                break
            d.rectangle([chipx, chipy, chipx + tw, chipy + 12], outline=(c[0] // 2, c[1] // 2, c[2] // 2))
            dtext(d, (chipx + 4, chipy + 6), lab, f_tiny, c, anchor="lm")
            chipx += tw + 4
            shown += 1
        if shown < len(ents):
            dtext(d, (W - 36, chipy + 6), f"+{len(ents) - shown}", f_tiny, c, anchor="rm")

    # x15 lane — the bound-in move, highlighted as the sweep's climax
    d.line([(28, 470), (W - 28, 470)], fill=LINE, width=1)
    dtext(d, (28, 482), "x15 · ASIMOV LANE BOUND INTO ORIGIN", f_eyebrow, EMERALD)
    rise = max(0.0, min(1.0, (phase - 0.55) / 0.25))  # climbs in the last third
    cols = 3
    rowh = 44
    for i, e in enumerate(x15_all):
        col = EMERALD if e["a"] == 0 else (AXCOL[e["a"]] if e["a"] < 4 else VIOLET)
        if i > rise * len(x15_all):
            col = tuple(max(8, v // 5) for v in col)
        r, cidx = divmod(i, cols)
        bx = 28 + cidx * ((W - 56) // cols)
        by = 504 + r * rowh
        if by + rowh > 930:
            break
        d.rounded_rectangle([bx, by, bx + (W - 56) // cols - 8, by + rowh - 6],
                            radius=4, outline=col, width=1,
                            fill=(col[0] // 18, col[1] // 18, col[2] // 18))
        dtext(d, (bx + 6, by + 7), e["name"][:20], font(10, True), col)
        dtext(d, (bx + 6, by + 22), f"x{e['x']}:y{e['y']}:z{e['z']}:æ{e['a']}", f_tiny, MUTED)

    # footer
    dtext(d, (28, 950), "SOURCE ae-atlas.js · parsed live; github.io is surface truth", f_tiny, MUTED)
    dtext(d, (28, 970), "576×1024 · #050505 · #D4AF37 · #00ff9d", f_tiny, MUTED)
    return img


def main():
    atlas = load_atlas()
    frames = [frame(k, FRAMES, atlas) for k in range(FRAMES)]
    out = Path(__file__).parent / "github_io_atlas.gif"
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=90, loop=0, optimize=False, disposal=2)
    print(f"wrote {out} ({len(frames)} frames, {out.stat().st_size} bytes, "
          f"{len(atlas)} attrs parsed)")


if __name__ == "__main__":
    main()
