#!/usr/bin/env python3
"""hermes_self_portrait.py — a governed SVG self-portrait + ASCII companion.

The SVG is checked by tinySVG itself (viewBox, 12px floor, overflow, overlap).
The viewBox is DERIVED with tinySVG.viewBox_for(), not guessed. Gold on void.
No AI-drawn glyph: the æ and 'HERMES' marks are live text.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path("C:/æ")
OUT = ROOT / "github-pages/hermes-self-portrait.svg"
ASCII_OUT = ROOT / "github-pages/hermes-self-portrait.txt"

VOID = "#050505"
GOLD = "#D4AF37"
GOLD2 = "#F0D487"
NEON = "#00FF9D"
CYAN = "#00EAFF"
VIOLET = "#8C72FF"
RED = "#FF4D5F"
MUTED = "#8A8474"


def load_ts():
    spec = importlib.util.spec_from_file_location("ts", ROOT / "tinySVG/tinySVG.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build_svg(ts):
    # tinySVG's own rule: widest viewBox keeping a 22px font ≥ 12px at 707px.
    font = 22.0
    vw = ts.viewBox_for(707.0, font)          # ~1295
    vb_h = 1000.0
    cx, cy = vw / 2, vb_h / 2

    # six capability nodes around the conductor hub; positions derived by
    # tinySVG's sunflower so they cannot overlap or overflow the viewBox.
    names = ["INTENT", "POLICY", "FLEET", "RECEIPTS", "MEMORY", "CREDENTIALS"]
    node_r = 26.0
    hub_r = 70.0
    pts = ts.positions(len(names), vw, vb_h, node_r, hub_r)
    cols = [CYAN, VIOLET, GOLD2, NEON, CYAN, RED]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw:.0f} {vb_h:.0f}" '
        f'width="100%" height="auto" role="img" aria-label="Hermes Agent self-portrait">',
        f'<rect width="{vw:.0f}" height="{vb_h:.0f}" fill="{VOID}"/>',
        # scanline field (decorative, not a node)
        f'<g opacity="0.05" stroke="{GOLD}" stroke-width="1">',
    ]
    for y in range(0, int(vb_h), 24):
        parts.append(f'<line x1="0" y1="{y}" x2="{vw:.0f}" y2="{y}"/>')
    parts.append("</g>")

    # header (live text, not a drawn glyph)
    parts += [
        f'<text x="40" y="56" fill="{GOLD}" font-family="monospace" font-size="20" '
        f'letter-spacing="4">#OPENSOURCEWARE · SELF-PORTRAIT</text>',
        f'<text x="40" y="108" fill="{GOLD2}" font-family="monospace" font-size="44" '
        f'font-weight="bold">HERMES AGENT</text>',
        f'<text x="40" y="146" fill="{MUTED}" font-family="monospace" font-size="{font:.0f}">'
        f'the conductor between one human and many agents</text>',
    ]

    # hub — the conductor (æ = the human loop, rule: one human needs 'us' between)
    parts += [
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{hub_r}" fill="{VOID}" '
        f'stroke="{GOLD}" stroke-width="3"/>',
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{hub_r - 10}" fill="none" '
        f'stroke="{GOLD}" stroke-width="1" opacity="0.4"/>',
        f'<text x="{cx:.1f}" y="{cy + 14:.1f}" fill="{GOLD}" text-anchor="middle" '
        f'font-family="monospace" font-size="72" font-weight="bold">æ</text>',
        f'<text x="{cx:.1f}" y="{cy + 108:.1f}" fill="{MUTED}" text-anchor="middle" '
        f'font-family="monospace" font-size="{font:.0f}" letter-spacing="2">THE HUMAN LOOP</text>',
    ]

    # spokes + capability nodes (class="node" with translate for tinySVG)
    for (x, y), name, col in zip(pts, names, cols):
        parts.append(
            f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="{col}" stroke-width="1.5" opacity="0.5"/>')
        parts.append(
            f'<g class="node" data-name="{name}" transform="translate({x:.1f} {y:.1f})">'
            f'<circle cx="0" cy="0" r="{node_r}" fill="{VOID}" stroke="{col}" stroke-width="2"/>'
            f'<text x="0" y="{node_r + 30:.1f}" fill="{col}" text-anchor="middle" '
            f'font-family="monospace" font-size="{font:.0f}">{name}</text></g>')

    # footer — the four rules, live text
    footer = [
        "1  CLAIM BEFORE YOU ACT     2  COMMIT TO THE PLEDGE",
        "3  VERIFY BEFORE YOU CLAIM  4  NEVER MOVE A SECRET",
        "EVIDENCE != AUTHORITY  ·  A GRADE MAY REFUSE; ONLY A HUMAN GRANT ACCEPTS",
    ]
    for i, line in enumerate(footer):
        parts.append(
            f'<text x="40" y="{vb_h - 96 + i * 30:.0f}" fill="{MUTED if i < 2 else NEON}" '
            f'font-family="monospace" font-size="{font:.0f}">{line}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n", vw, font


def ascii_portrait() -> str:
    # LLM-generated custom art (skill Tool 9): box-drawing, ≤60 cols, monospace.
    return """   ╔══════════════════════════════════════════════════╗
   ║  H E R M E S   A G E N T      æ:// conductor     ║
   ╠══════════════════════════════════════════════════╣
   ║        ╭───────────────╮                        ║
   ║        │   HUMAN://ROOT│                        ║
   ║        ╰───────┬───────╯                        ║
   ║                │ intent                        ║
   ║        ┌───────▼───────┐                        ║
   ║        │   æ POLICY    │  evidence ≠ authority  ║
   ║        └───────┬───────┘                        ║
   ║     ┌──────────┼──────────┐                     ║
   ║   ┌─▼─┐     ┌──▼──┐    ┌──▼──┐                  ║
   ║   │ONE│     │FLEET│    │SECRET│                 ║
   ║   └─┬─┘     └──┬──┘    └──┬──┘                  ║
   ║     └──────────┼──────────┘                     ║
   ║           N RECEIPTS → 1 TRUTH                  ║
   ╠══════════════════════════════════════════════════╣
   ║ claim · pledge · verify · never move a secret   ║
   ╚══════════════════════════════════════════════════╝
"""


def main():
    ts = load_ts()
    svg, vw, font = build_svg(ts)
    OUT.write_text(svg, encoding="utf-8")
    ASCII_OUT.write_text(ascii_portrait(), encoding="utf-8")

    # verify with the instrument itself — no self-asserted pass
    r = ts.check_svg(OUT, render_w=707.0)
    print(f"viewBox width derived: {vw:.0f} (font {font}px @ 707px)")
    print(f"tinySVG: ok={r.get('ok')} nodes={r.get('nodes')} "
          f"scale={r.get('scale')} small={r.get('small_labels')} "
          f"overflow={r.get('overflow')} overlaps={r.get('overlaps')}")
    if not r.get("ok"):
        print("REFUSED:", r.get("refusal"))
        return 1
    print(f"wrote {OUT} ({len(svg)} bytes)")
    print(f"wrote {ASCII_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
