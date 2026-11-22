#!/usr/bin/env python3
"""tinySVG — the sovereign instrument for vector surfaces.

tinySVG does NOT draw pictures. It GOVERNS the one thing that made a 20-node
constellation unreadable: **the viewBox is not the screen.** It measures the
render width, derives the scale, and refuses a surface whose type would fall
below the legibility floor or whose nodes would overlap.

    doctor()      build a 20-node constellation at a real chat width and check it
    check <svg>   measure a file: overflow, node overlap, effective font size
    constellation emit a layout that self-sizes its viewBox to the render width
    grade         two renders, byte-compared

Invariants (tiny* family): doctor() measures; every verb refuses; the contract is
read from the artifact; a receipt is a claim until re-run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

LEDGER = Path(os.environ.get("TINYSVG_LEDGER", r"C:\æ\logs\tinySVG.jsonl"))
GENESIS = "0" * 64

#: the floor. Below this the eye stops reading a label in a dense graph.
MIN_FONT_PX = 12.0
#: a node's ring must clear the hub by this much, in viewBox units.
HUB_CLEARANCE = 12.0

SVG_NS = "{http://www.w3.org/2000/svg}"


def _canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ── geometry ───────────────────────────────────────────────────────────────

def positions(n: int, w: float, h: float, node_r: float, hub_r: float) -> list[tuple[float, float]]:
    """Fibonacci (sunflower), sized so the innermost node clears the hub and the
    outermost stays inside the viewBox."""
    lo = hub_r + node_r + HUB_CLEARANCE
    # solve the growth step so the outermost fits both axes
    k = math.sqrt(max(n - 1, 0))
    fit = min((w / 2 - node_r - 8) / 1.55, (h / 2 - node_r - 8) / 1.05)
    step = max((fit - lo) / k, 6.0) if k else 0.0
    cx, cy = w / 2, h / 2
    golden = math.pi * (3 - math.sqrt(5))
    return [(cx + (lo + step * math.sqrt(i)) * math.cos(i * golden) * 1.55,
             cy + (lo + step * math.sqrt(i)) * math.sin(i * golden) * 1.05)
            for i in range(n)]


def viewBox_for(render_w: float, font: float, base: float = 1000.0) -> float:
    """The widest viewBox that keeps `font` at or above MIN_FONT_PX on screen."""
    return math.floor(render_w * font / MIN_FONT_PX)


# ── the check ──────────────────────────────────────────────────────────────

def check_svg(path: Path | str, render_w: float | None = None) -> dict:
    """Measure a surface. Reads the artifact, never the filename."""
    path = Path(path)
    if not path.exists():
        return {"ok": False, "refusal": f"no such file: {path}"}
    raw = path.read_bytes()
    # an HTML surface wraps its SVG; measure the ARTIFACT, so extract the block
    # instead of refusing a page that is not bare XML.
    head = raw.lstrip()[:200].lower()
    if not head.startswith(b"<svg") and b"<svg" in raw:
        s = raw.index(b"<svg")
        e = raw.lower().rindex(b"</svg>") + len(b"</svg>")
        raw = raw[s:e]
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return {"ok": False, "refusal": f"SVG no parsea: {exc}"}

    vb = root.get("viewBox") or root.get("viewbox")
    if not vb:
        return {"ok": False, "refusal": "sin viewBox — no hay forma de derivar la escala"}
    try:
        vx, vy, vw, vh = [float(v) for v in vb.replace(",", " ").split()]
    except ValueError:
        return {"ok": False, "refusal": f"viewBox ilegible: {vb!r}"}
    if vw <= 0 or vh <= 0:
        return {"ok": False, "refusal": f"viewBox degenerado: {vb!r}"}

    out = {"ok": True, "viewBox": [vx, vy, vw, vh], "render_w": render_w}
    if render_w is None:
        render_w = vw
    scale = render_w / vw
    out["scale"] = round(scale, 4)

    nodes = []
    for g in root.iter():
        if (g.get("class") or "") != "node":
            continue
        tr = g.get("transform") or ""
        try:
            nums = [float(n) for n in
                    __import__("re").findall(r"-?\d+(?:\.\d+)?", tr.split("translate")[-1])]
            x, y = nums[0], nums[1]
        except (IndexError, ValueError):
            continue
        r = 0.0
        fs = 0.0
        for c in g.iter():
            if c.tag.endswith("circle") and r == 0.0:
                r = float(c.get("r") or 0)
            if c.tag.endswith("text") and fs == 0.0:
                fs = float(c.get("font-size") or 0)
        nodes.append({"name": g.get("data-name"), "x": x, "y": y, "r": r, "font": fs})

    out["nodes"] = len(nodes)

    # 1. effective type size — the lesson of this instrument
    small = [n["name"] for n in nodes if n["font"] and n["font"] * scale < MIN_FONT_PX]
    out["font_floor_px"] = round(MIN_FONT_PX, 1)
    out["small_labels"] = small

    # 2. overflow
    over = [n["name"] for n in nodes
            if n["x"] - n["r"] < vx - 1 or n["x"] + n["r"] > vx + vw + 1
            or n["y"] - n["r"] < vy - 1 or n["y"] + n["r"] > vy + vh + 1]
    out["overflow"] = over

    # 3. node-on-node overlap
    hits = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
            if d < a["r"] + b["r"]:
                hits.append([a["name"], b["name"], round(d, 1)])
    out["overlaps"] = hits

    ok = not small and not over and not hits
    out["ok"] = ok
    if not ok:
        out["refusal"] = ", ".join(
            [f"{len(small)} etiquetas bajo el suelo de legibilidad"] if small else [] +
            [f"{len(over)} nodos fuera del viewBox"] if over else [] +
            [f"{len(hits)} solapes de nodos"] if hits else [])
    return out


# ── emitter ────────────────────────────────────────────────────────────────

def constellation(names: list[str], render_w: float = 707.0,
                   font: float = 27.0, node_r: float = 58.0) -> str:
    """Emit a constellation whose viewBox is chosen so `font` survives the render."""
    vw = viewBox_for(render_w, font)
    vh = round(vw * 0.65)
    hub = round(node_r * 2.2)
    pts = positions(len(names), vw, vh, node_r, hub)
    golden = math.pi * (3 - math.sqrt(5))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
             f'role="img" aria-label="constelacion">']
    parts.append(f'<circle cx="{vw/2}" cy="{vh/2}" r="{hub}" fill="none" '
                 f'stroke="rgba(212,175,55,.28)"/>')
    for name, (x, y) in zip(names, pts):
        a = (names.index(name) * golden) % (2 * math.pi)
        parts.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{vw/2}" y2="{vh/2}" '
                     f'stroke="#D4AF37" stroke-opacity=".15"/>')
        parts.append(f'<g class="node" data-name="{name}" '
                     f'transform="translate({x:.1f},{y:.1f})">'
                     f'<circle r="{node_r}" fill="rgba(5,5,5,.72)" stroke="#D4AF37" '
                     f'stroke-width="2.2"/>'
                     f'<text y="9" text-anchor="middle" fill="#e8e8e8" '
                     f'font-size="{font}" font-family="monospace">{name}</text></g>')
    parts.append("</svg>")
    return "\n".join(parts)


# ── doctor ─────────────────────────────────────────────────────────────────

def doctor() -> dict:
    out = {"ok": False, "checks": {}}
    names = [f"n{i}" for i in range(20)]
    with tempfile.TemporaryDirectory() as td:
        svg = Path(td) / "probe.svg"
        # a real chat-column width, not a comfortable desktop one
        svg.write_text(constellation(names, render_w=707.0), encoding="utf-8")
        r = check_svg(svg, render_w=707.0)
        out["checks"]["render_w"] = 707
        out["checks"]["viewBox"] = r.get("viewBox")
        out["checks"]["scale"] = r.get("scale")
        out["checks"]["nodes"] = r.get("nodes")
        out["checks"]["small_labels"] = len(r.get("small_labels") or [])
        out["checks"]["overflow"] = len(r.get("overflow") or [])
        out["checks"]["overlaps"] = len(r.get("overlaps") or [])
        if not r.get("ok"):
            out["checks"]["refusal"] = r.get("refusal")
            return out
        out["ok"] = True
        out["checks"]["font_effective_px"] = round(27.0 * r["scale"], 1)
    out["note"] = "medido en esta maquina, no asumido"
    return out


def grade(render_w: float = 707.0) -> dict:
    names = [f"n{i}" for i in range(20)]
    a = constellation(names, render_w=render_w)
    b = constellation(names, render_w=render_w)
    ha, hb = _sha(a.encode()), _sha(b.encode())
    return {"ok": ha == hb, "deterministic": ha == hb,
            "sha256_a": ha, "sha256_b": hb,
            "note": "dos emisiones, byte a byte. Un SVG debe ser reproducible."}


# ── ledger ─────────────────────────────────────────────────────────────────

def ledger_append(decision: str, payload: dict) -> dict:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    recs = ledger_read()
    prev = recs[-1]["hash"] if recs else GENESIS
    r = {"decision": decision, "payload": payload, "prev": prev}
    r["hash"] = _sha(_canon(r))
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return r


def ledger_read() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def ledger_verify() -> dict:
    recs = ledger_read()
    prev = GENESIS
    for r in recs:
        body = {k: v for k, v in r.items() if k != "hash"}
        if r.get("prev") != prev or r.get("hash") != _sha(_canon(body)):
            return {"chain_ok": False, "broken_at": r.get("decision"), "records": len(recs)}
        prev = r["hash"]
    return {"chain_ok": True, "records": len(recs),
            "head": recs[-1]["hash"][:12] if recs else GENESIS[:12]}


def main() -> int:
    ap = argparse.ArgumentParser(prog="tinySVG", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    c = sub.add_parser("check"); c.add_argument("svg"); c.add_argument("--render-w", type=float, default=None)
    s = sub.add_parser("constellation"); s.add_argument("names"); s.add_argument("--render-w", type=float, default=707.0)
    g = sub.add_parser("grade"); g.add_argument("--render-w", type=float, default=707.0)
    sub.add_parser("ledger")
    a = ap.parse_args()

    if a.cmd == "doctor":
        r = doctor(); print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("doctor", {"ok": r["ok"]}); return 0 if r["ok"] else 1
    if a.cmd == "check":
        r = check_svg(a.svg, a.render_w); print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["ok"] else 1
    if a.cmd == "constellation":
        names = [n.strip() for n in a.names.split(",") if n.strip()]
        print(constellation(names, render_w=a.render_w)); return 0
    if a.cmd == "grade":
        r = grade(a.render_w); print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("grade", {"deterministic": r["deterministic"]}); return 0 if r["ok"] else 1
    if a.cmd == "ledger":
        print(json.dumps(ledger_verify(), ensure_ascii=False, indent=1)); return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
