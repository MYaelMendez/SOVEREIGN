#!/usr/bin/env python3
"""tinyKÆNBÆN — the tiny family as a kanban board, measured not declared.

Source of truth: the RESULTS array already embedded in github-pages/tiny.html,
produced by tiny_family.py running every doctor on this machine. This script
NEVER re-runs a doctor and NEVER invents a status: it moves the measured
verdicts into three lanes.

    OK      doctor returned ok:true on every interpreter
    FLAKY   interpreters disagreed (a finding, not a pass)
    REFUSED doctor returned ok:false / a stale gate

    python tiny/tiny_kanban.py            -> writes github-pages/tiny-kanban.html
    python tiny/tiny_kanban.py --stdout   -> prints the HTML
"""
from __future__ import annotations

import argparse
import hashlib
import html as htmllib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiny_family  # noqa: E402  (FAMILY registry is the order/key source)

SOURCE = ROOT / "github-pages" / "tiny.html"
OUT = ROOT / "github-pages" / "tiny-kanban.html"
BACK = "https://myaelmendez.github.io/tiny.html"


def load_results() -> tuple[list[dict], str]:
    raw = SOURCE.read_text(encoding="utf-8")
    m = re.search(r"const RESULTS = (\[.*?\]);\s*\nconst FAMILY", raw, re.S)
    if not m:
        raise SystemExit("no measured RESULTS array in tiny.html — run tiny_family.py first")
    return json.loads(m.group(1)), hashlib.sha256(raw.encode("utf-8")).hexdigest()


def lane_of(r: dict) -> str:
    if r.get("flaky"):
        return "flaky"
    return "ok" if r.get("ok") else "refused"


def esc(s) -> str:
    return htmllib.escape(str(s), quote=True)


def verdict_line(r: dict) -> str:
    vs = r.get("verdicts") or []
    if not vs:
        return esc(r.get("refusal") or r.get("check") or "sin veredicto")
    return " · ".join(
        f"{esc(v.get('python', '?'))}:{'ok' if v.get('ok') else 'NO'}"
        f"{' ' + str(v['elapsed_s']) + 's' if v.get('elapsed_s') is not None else ''}"
        for v in vs
    )


def reason(r: dict) -> str:
    return esc(r.get("refusal") or r.get("check") or
               ", ".join(v.get("refusal", "") for v in (r.get("verdicts") or [])
                         if v.get("refusal")) or
               "todos los interpreters respondieron ok")


def card(name: str, dom: str, role: str, r: dict, i: int) -> str:
    lane = lane_of(r)
    badge = {"ok": "OK", "flaky": "FLAKY", "refused": "REFUSED"}[lane]
    return f"""<article class="card {lane}" data-name="{esc(name)}">
  <div class="top"><span class="num">{i:02d}</span><span class="badge {lane}">{badge}</span></div>
  <h3>{esc(name)}</h3>
  <div class="role">{esc(role)}</div>
  <div class="kv"><span class="k">dominio</span><span class="v">{esc(dom)}</span></div>
  <div class="kv"><span class="k">doctors</span><span class="v">{verdict_line(r)}</span></div>
  <div class="kv"><span class="k">motivo</span><span class="v">{reason(r)}</span></div>
  <a class="recibo" href="{BACK}" target="_blank" rel="noopener">ver recibo en tiny* →</a>
</article>"""


def render(results: list[dict], sha: str) -> str:
    counts = {k: sum(1 for r in results if lane_of(r) == k)
              for k in ("ok", "flaky", "refused")}
    lanes: dict[str, list[str]] = {"ok": [], "flaky": [], "refused": []}
    for i, (name, dom, role) in enumerate(tiny_family.FAMILY, 1):
        r = results[i - 1] if i - 1 < len(results) else {}
        lanes[lane_of(r)].append(card(name, dom, role, r, i))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cols = "".join(f"""<section class="lane {k}">
  <header><h2>{t}</h2><span class="cnt">{counts[k]}</span></header>
  <div class="stack">{''.join(lanes[k]) or '<div class="empty">sin tarjetas — ningún doctor cayó aquí</div>'}</div>
</section>""" for k, t in (("ok", "VERDE · verificado"),
                          ("flaky", "AMARILLO · desacuerdo"),
                          ("refused", "ROJO · negativa")))
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>tiny* kænbæn · la familia, medida</title>
<meta name="description" content="{counts['ok']} de {len(results)} instrumentos tiny* en verde. Tablero derivado de los doctors reales, no declarado.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=JetBrains+Mono:wght@300;400;700&display=swap" rel="stylesheet">
<style>
:root{{--void:#050505;--gold:#D4AF37;--text:#e8e8e8;--mut:#a89e80;--line:rgba(212,175,55,.24);--neon:#39ff14;--red:#ff6b6b;--amber:#ffd166}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--void);color:var(--text);font-family:'JetBrains Mono',ui-monospace,monospace;min-height:100vh}}
body::before{{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;opacity:.5;
 background:repeating-linear-gradient(0deg,rgba(212,175,55,.03) 0 1px,transparent 1px 4px)}}
.wrap{{position:relative;z-index:1;max-width:1500px;margin:0 auto;padding:clamp(14px,2.4vw,30px)}}
header.top{{display:flex;justify-content:space-between;align-items:flex-end;gap:18px;flex-wrap:wrap;padding-bottom:16px;border-bottom:1px solid var(--line)}}
.eyebrow{{font-size:.66rem;letter-spacing:.4em;text-transform:uppercase;color:var(--gold)}}
h1{{font-family:Orbitron,sans-serif;font-weight:900;font-size:clamp(2rem,5vw,3.2rem);color:var(--gold);margin-top:8px;line-height:.95}}
.sub{{color:var(--mut);font-size:.78rem;margin-top:10px;max-width:640px;line-height:1.6}}
.score{{text-align:right;font-family:Orbitron,sans-serif;color:var(--gold);font-size:clamp(1.8rem,4vw,3rem);font-weight:900}}
.score small{{display:block;font-family:'JetBrains Mono',monospace;font-size:.62rem;letter-spacing:.2em;color:var(--mut);font-weight:400;margin-top:6px}}
.board{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:20px;align-items:start}}
@media(max-width:900px){{.board{{grid-template-columns:1fr}}}}
.lane{{border:1px solid var(--line);border-radius:14px;background:rgba(9,8,4,.7);padding:14px;min-height:180px}}
.lane header{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px dashed var(--line);padding-bottom:10px;margin-bottom:12px}}
.lane h2{{font-family:Orbitron,sans-serif;font-size:.72rem;letter-spacing:.18em;color:var(--gold)}}
.lane.flaky h2{{color:var(--amber)}} .lane.refused h2{{color:var(--red)}}
.cnt{{font-family:Orbitron,sans-serif;font-size:1.3rem;font-weight:900;color:var(--gold)}}
.lane.flaky .cnt{{color:var(--amber)}} .lane.refused .cnt{{color:var(--red)}}
.stack{{display:flex;flex-direction:column;gap:10px}}
.card{{border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:9px;padding:11px 13px;background:rgba(0,0,0,.45)}}
.card.flaky{{border-left-color:var(--amber)}} .card.refused{{border-left-color:var(--red)}}
.top{{display:flex;justify-content:space-between;align-items:center}}
.num{{font-size:.6rem;color:var(--mut);letter-spacing:.14em}}
.badge{{font-size:.56rem;letter-spacing:.14em;padding:3px 7px;border:1px solid currentColor;border-radius:999px;color:var(--gold)}}
.badge.flaky{{color:var(--amber)}} .badge.refused{{color:var(--red)}}
.card h3{{font-family:Orbitron,sans-serif;font-size:.86rem;color:var(--text);margin:6px 0 2px}}
.role{{font-size:.66rem;color:var(--mut);margin-bottom:8px;min-height:1.1em}}
.kv{{display:flex;justify-content:space-between;gap:10px;font-size:.63rem;padding:4px 0;border-top:1px dashed rgba(212,175,55,.12)}}
.kv .k{{color:var(--mut);flex:0 0 58px}} .kv .v{{color:var(--gold);text-align:right;word-break:break-word}}
.recibo{{display:inline-block;margin-top:9px;font-size:.62rem;color:var(--gold);text-decoration:none;border-bottom:1px solid var(--line)}}
.recibo:hover{{color:#fff}}
.empty{{font-size:.7rem;color:var(--mut);border:1px dashed var(--line);border-radius:8px;padding:16px;text-align:center}}
footer{{margin-top:22px;padding-top:14px;border-top:1px solid var(--line);font-size:.64rem;color:var(--mut);display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}}
code{{color:#ffd966}}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div>
      <div class="eyebrow">æ:// tiny* · kænbæn</div>
      <h1>tiny*kænbæn</h1>
      <p class="sub">Cada tarjeta es un instrumento. Cada carril es un veredicto real de <code>tiny_family.py</code>. Ningún estado fue escrito a mano: los doctors corrieron en esta máquina.</p>
    </div>
    <div class="score">{counts['ok']}/{len(results)}<small>{counts['ok']} limpios · {counts['flaky']} con desacuerdo · {counts['refused']} negativa</small></div>
  </header>
  <div class="board">{cols}</div>
  <footer>
    <span>fuente: <code>tiny.html</code> · sha256 <code>{sha[:16]}</code> · generado {esc(now)}</span>
<span><a href="https://myaelmendez.github.io/kanban-unified.html" style="color:var(--gold);text-decoration:none">kænbæn unificado →</a> · <a href="truth.json" style="color:var(--gold);text-decoration:none">truth.json →</a> · <a href="{BACK}" style="color:var(--gold);text-decoration:none">← volver a la constelación tiny*</a></span>
  </footer>
</div>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="tinyKÆNBÆN — board from measured doctors")
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args()
    results, sha = load_results()
    board = render(results, sha)
    if a.stdout:
        print(board)
    else:
        OUT.write_text(board, encoding="utf-8")
        counts = {k: sum(1 for r in results if lane_of(r) == k)
                  for k in ("ok", "flaky", "refused")}
        print(f"tiny*kænbæn -> {OUT}  {len(board.encode()):,} bytes · "
              f"ok={counts['ok']} flaky={counts['flaky']} refused={counts['refused']} · "
              f"source sha256:{sha[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
