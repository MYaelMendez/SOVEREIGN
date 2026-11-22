#!/usr/bin/env python3
"""tinySVG demo — a surface that demonstrates the instrument's own rule.

It draws the lesson: the viewBox is not the screen. The same label at 27 units
is 12.0 px on a 707 px chat column and 21.6 px on a 1280 px monitor. Every number
on it is derived from `viewBox_for`, so the picture cannot drift from the rule.

    python demo.py                # writes demo.svg
    python demo.py --stdout       # prints it
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tinySVG  # noqa: E402

GOLD = "#D4AF37"
VOID = "#050505"
INK = "#e8e8e8"
DIM = "#a3926a"


def demo_svg(render_w: float = 707.0) -> str:
    font = 27.0
    vw = tinySVG.viewBox_for(render_w, font)
    scale = render_w / vw
    eff = font * scale

    # the same label on a desktop monitor
    desk_w = 1280.0
    desk_vw = tinySVG.viewBox_for(desk_w, font)
    desk_eff = font * (desk_w / desk_vw)

    W = vw
    H = round(vw * 0.52)
    s = []
    A = s.append
    A(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
      f'role="img" aria-label="demostracion: el viewBox no es la pantalla">')
    A(f'<rect width="{W}" height="{H}" fill="{VOID}"/>')
    A(f'<rect width="{W}" height="{H}" fill="none" stroke="{GOLD}" stroke-opacity=".35"/>')

    # title
    A(f'<text x="{W/2}" y="{H*0.09:.0f}" text-anchor="middle" fill="{GOLD}" '
      f'font-size="{font*1.5:.0f}" font-family="monospace" font-weight="bold">'
      f'el viewBox no es la pantalla</text>')
    A(f'<text x="{W/2}" y="{H*0.155:.0f}" text-anchor="middle" fill="{DIM}" '
      f'font-size="{font*0.85:.0f}" font-family="monospace">'
      f'una etiqueta de {font:.0f} unidades, medida en dos anchos de render</text>')

    # the two boxes: viewBox vs screen
    box_top = H * 0.24
    box_h = H * 0.30
    left_w = W * 0.34
    right_w = W * 0.20
    lx = W * 0.06
    rx = W * 0.72
    A(f'<rect x="{lx:.0f}" y="{box_top:.0f}" width="{left_w:.0f}" height="{box_h:.0f}" '
      f'fill="rgba(212,175,55,.08)" stroke="{GOLD}" stroke-width="2.5"/>')
    A(f'<text x="{lx+left_w/2:.0f}" y="{box_top+box_h*0.42:.0f}" text-anchor="middle" '
      f'fill="{INK}" font-size="{font*0.95:.0f}" font-family="monospace">viewBox {vw:.0f}</text>')
    A(f'<text x="{lx+left_w/2:.0f}" y="{box_top+box_h*0.78:.0f}" text-anchor="middle" '
      f'fill="{DIM}" font-size="{font*0.8:.0f}" font-family="monospace">lo que el autor dibuja</text>')

    # the scale arrow
    ay = box_top + box_h / 2
    A(f'<line x1="{lx+left_w+18:.0f}" y1="{ay:.0f}" x2="{rx-18:.0f}" y2="{ay:.0f}" '
      f'stroke="{GOLD}" stroke-width="3" marker-end="url(#ah)"/>')
    A(f'<defs><marker id="ah" markerWidth="12" markerHeight="12" refX="9" refY="5" '
      f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{GOLD}"/></marker></defs>')
    A(f'<text x="{(lx+left_w+rx)/2:.0f}" y="{ay-16:.0f}" text-anchor="middle" fill="{GOLD}" '
      f'font-size="{font:.0f}" font-family="monospace">× {scale:.4f}</text>')

    A(f'<rect x="{rx:.0f}" y="{box_top:.0f}" width="{right_w:.0f}" height="{box_h:.0f}" '
      f'fill="rgba(123,223,242,.08)" stroke="#7bdff2" stroke-width="2.5"/>')
    A(f'<text x="{rx+right_w/2:.0f}" y="{box_top+box_h*0.42:.0f}" text-anchor="middle" '
      f'fill="{INK}" font-size="{font*0.95:.0f}" font-family="monospace">pantalla {render_w:.0f}</text>')
    A(f'<text x="{rx+right_w/2:.0f}" y="{box_top+box_h*0.78:.0f}" text-anchor="middle" '
      f'fill="#7bdff2" font-size="{font*1.25:.0f}" font-family="monospace" font-weight="bold">'
      f'{eff:.1f} px</text>')

    # the rule
    ry = H * 0.66
    A(f'<rect x="{W*0.06:.0f}" y="{ry:.0f}" width="{W*0.88:.0f}" height="{H*0.12:.0f}" '
      f'fill="rgba(5,5,5,.6)" stroke="{GOLD}" stroke-opacity=".4"/>')
    A(f'<text x="{W/2:.0f}" y="{ry+H*0.075:.0f}" text-anchor="middle" fill="{INK}" '
      f'font-size="{font*0.92:.0f}" font-family="monospace">'
      f'viewBox = render × fuente ÷ suelo = {render_w:.0f} × {font:.0f} ÷ '
      f'{tinySVG.MIN_FONT_PX:.0f} = {vw:.0f}</text>')

    # the two measured cases
    ty = H * 0.845
    A(f'<text x="{W*0.06:.0f}" y="{ty:.0f}" fill="{DIM}" font-size="{font*0.8:.0f}" '
      f'font-family="monospace">chat 707 px  →  viewBox {vw:.0f}  →  {eff:.1f} px  '
      f'·  monitor 1280 px  →  viewBox {desk_vw:.0f}  →  {desk_eff:.1f} px</text>')
    A(f'<text x="{W*0.06:.0f}" y="{ty+H*0.075:.0f}" fill="{DIM}" font-size="{font*0.8:.0f}" '
      f'font-family="monospace">tipo &lt; {tinySVG.MIN_FONT_PX:.0f} px  →  REFUSADO '
      f'(tiny.html publico 11.93 px con viewBox 1600; tinySVG lo rechazo)</text>')
    A('</svg>')
    return "\n".join(s)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--render-w", type=float, default=707.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args()
    svg = demo_svg(a.render_w)
    if a.stdout:
        print(svg)
        return 0
    out = Path(a.out) if a.out else Path(__file__).resolve().parent / "demo.svg"
    out.write_text(svg, encoding="utf-8")
    r = tinySVG.check_svg(out, render_w=a.render_w)
    print(f"{out}  {len(svg.encode()):,} bytes  check={'ok' if r['ok'] else 'REFUSED: ' + r.get('refusal','')}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
