#!/usr/bin/env python3
"""tiny* family — the constellation surface generator.

Runs every tiny* instrument's `doctor` and renders one constellation: each node
is an instrument, its colour its domain, its ring whether it measured ok. A
family member that could not be executed is shown as such — never as a pass.

    python tiny_family.py            # -> tiny.html
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\æ")
OUT = ROOT / "github-pages" / "tiny.html"

# name -> (domain, one-line role)
FAMILY = [
    ("tinycuda",     "pixels",   "raster determinista en una libreta GPU"),
    ("tinygpu",      "pixels",   "renderer de robot con CAD real"),
    ("tinycudavideo","video",    "el seam: frames -> pelicula"),
    ("tinyvision",   "video",    "supervision del film de la politica"),
    ("tinyffmpeg",   "codecs",   "gobierna los builds de FFmpeg"),
    ("tinyqr",       "identity", "el chip: firma de extremo a extremo"),
    ("tinymujoco",   "motion",   "fisica y movimiento"),
    ("tinyasimov",   "motion",   "el cuerpo: C2 con gates"),
    ("tinypython",   "policy",   "la politica que camina"),
    ("tinypolicy",   "policy",   "su C2"),
    ("tinyonnx",     "policy",   "el oracle ONNX"),
    ("tinycan",      "bus",      "el bus del robot"),
    ("tinygpugbot",  "actors",   "actores con cues, desde trazas"),
    ("tinycontinuum","time",     "el tiempo y sus frames"),
    ("tinyfilmmemory","memory",  "la memoria del film"),
    ("tinylab",      "lab",      "el auto-estudio de la familia"),
    ("tinyplugin",   "plugin",   "fallos de instalacion, a la vista"),
    ("tinyrepofilm", "film",     "un repo, org o usuario -> pelicula sellada"),
    ("tinyvoca",     "voice",    "la voz local que narra los films"),
    ("tinyae",       "protocol", "la familia measure-and-refuse, un solo prefijo"),
]

DOMAINS = {
    "pixels":  "#D4AF37",
    "video":   "#00e5ff",
    "codecs":  "#39ff14",
    "identity":"#ff4d6d",
    "motion":  "#bf5af2",
    "policy":  "#ffd166",
    "bus":     "#69d2ff",
    "actors":  "#ff9f5a",
    "time":    "#9bf6ff",
    "memory":  "#c8b6ff",
    "lab":     "#7CFC00",
    "plugin":  "#8d99ae",
    "film":    "#ffd700",
    "voice":   "#ff8fab",
    "protocol":"#D4AF37",
}


GPU_PY = r"C:\gpu\Scripts\python.exe"


def _interpreters() -> list[str]:
    """Three interpreters on this host carry different stacks:
      C:\\gpu\\Scripts\\python.exe          cupy + mujoco + onnxruntime
      hermes venv ...\\hermes-agent\\venv      qrcode + pyzbar + cv2
      sys.executable                          whatever launched the generator
    Each instrument is tried in order until one measures ok; the last result is
    kept so a machine missing one still reports honestly."""
    cands = [
        GPU_PY,
        r"C:\Users\yaelm\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe",
        sys.executable,
    ]
    out = []
    for c in cands:
        if c and Path(c).exists() and c not in out:
            out.append(c)
    return out


def run_doctor(name: str) -> dict:
    py = ROOT / name / f"{name}.py"
    if not py.exists():
        return {"ok": False, "refusal": f"{py} no existe"}
    last = None
    for exe in _interpreters():
        t0 = time.time()
        try:
            r = subprocess.run([exe, str(py), "doctor"],
                               capture_output=True, text=True, timeout=120, errors="replace")
        except Exception as exc:
            last = {"ok": False, "refusal": f"{type(exc).__name__}: {exc}"}
            continue
        dt = round(time.time() - t0, 2)
        out = (r.stdout or "").strip()
        try:
            d = json.loads(out)
        except Exception:
            last = {"ok": False, "refusal": f"stdout no es JSON: {out[:120]}",
                    "rc": r.returncode, "elapsed_s": dt}
            continue
        d["_elapsed_s"] = dt
        d["_rc"] = r.returncode
        d["_python"] = Path(exe).name
        if d.get("ok"):
            return d
        last = d
    return last or {"ok": False, "refusal": "sin interprete"}


def positions(n: int, w: int, h: int) -> list[tuple[float, float]]:
    """Fibonacci (sunflower) — deterministic, no random.

    The inner radius starts at 150 so the first node clears the r=86 core ring;
    the earlier 62*sqrt(0.5) put the innermost node at ~44 and the core text
    painted straight over it."""
    cx, cy = w / 2, h / 2
    golden = math.pi * (3 - math.sqrt(5))
    pts = []
    for i in range(n):
        r = 150.0 + 64.0 * math.sqrt(i)
        a = i * golden
        pts.append((cx + r * math.cos(a) * 1.55, cy + r * math.sin(a) * 1.05))
    return pts


def esc(x) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(results: list[dict], total_ok: int, elapsed: float) -> str:
    W, H = 1500, 980
    pts = positions(len(FAMILY), W, H)
    nodes, lines = [], []
    for (name, dom, role), (x, y), r in zip(FAMILY, pts, results):
        col = DOMAINS.get(dom, "#8d99ae")
        ok = bool(r.get("ok"))
        ring = col if ok else "#ff6b6b"
        nodes.append(
            f'<g class="node" data-name="{esc(name)}" data-dom="{esc(dom)}" data-ok="{str(ok).lower()}" '
            f'data-role="{esc(role)}" transform="translate({x:.1f},{y:.1f})" style="cursor:pointer">'
            f'<circle r="34" fill="rgba(5,5,5,.72)" stroke="{ring}" stroke-width="1.6" '
            f'style="transition:r .3s"/>'
            f'<circle r="4" fill="{col}" y="-24"/>'
            f'<text y="5" text-anchor="middle" fill="#e8e8e8" font-size="12" '
            f'font-family="JetBrains Mono,monospace">{esc(name.replace("tiny",""))}</text>'
            f'<text y="22" text-anchor="middle" fill="{col}" font-size="9" '
            f'font-family="JetBrains Mono,monospace">{esc("ok" if ok else "refused")}</text>'
            f'</g>')
        lines.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{W/2}" y2="{H/2}" '
                     f'stroke="{col}" stroke-opacity=".13" stroke-width="1"/>')

    legend = []
    seen = []
    for _, dom, _ in FAMILY:
        if dom not in seen:
            seen.append(dom)
            legend.append(f'<span class="lg"><i style="background:{DOMAINS.get(dom,"#8d99ae")}"></i>{esc(dom)}</span>')

    detail = []
    for (name, dom, role), r in zip(FAMILY, results):
        body = json.dumps(r, ensure_ascii=False, indent=1, default=str)
        detail.append(
            f'<pre class="det" id="det-{esc(name)}" hidden>{esc(body)}</pre>')

    payload = json.dumps(results, ensure_ascii=False, default=str)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>tiny* · la familia soberana</title>
<meta rel="canonical" href="https://myaelmendez.github.io/tiny.html">
<meta name="description" content="Los 18 instrumentos tiny* del fleet, como una constelación ejecutable: cada nodo corrio su doctor real. Medido, no declarado.">
<meta property="og:title" content="tiny* · la familia soberana">
<meta property="og:type" content="website">
<meta property="og:url" content="https://myaelmendez.github.io/tiny.html">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=JetBrains+Mono:wght@300;400;700&display=swap" rel="stylesheet">
<style>
:root{{--void:#050505;--gold:#D4AF37;--text:#e8e8e8;--dim:#a3926a;--mut:#a89e80;--line:rgba(212,175,55,.24);--neon:#39ff14;--red:#ff6b6b}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--void);color:var(--text);font-family:'JetBrains Mono',ui-monospace,monospace;min-height:100vh;overflow-x:hidden}}
body::before{{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;background:
 radial-gradient(1000px 700px at 50% 45%,rgba(212,175,55,.10),transparent 62%),
 radial-gradient(700px 500px at 8% 92%,rgba(0,229,255,.06),transparent 60%)}}
body::after{{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.5;
 background:repeating-linear-gradient(0deg,rgba(212,175,55,.03) 0 1px,transparent 1px 4px)}}
.wrap{{position:relative;z-index:1;max-width:1280px;margin:0 auto;padding:clamp(14px,2.6vw,34px)}}
header{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;flex-wrap:wrap;
 padding-bottom:18px;border-bottom:1px solid var(--line)}}
.eyebrow{{font-size:clamp(.58rem,1.1vw,.72rem);letter-spacing:.4em;text-transform:uppercase;color:var(--gold)}}
h1{{font-family:'Orbitron',sans-serif;font-weight:900;font-size:clamp(1.7rem,5vw,3.4rem);color:var(--gold);
 letter-spacing:-.02em;line-height:.95;margin-top:10px;text-shadow:0 0 50px rgba(212,175,55,.26)}}
.sub{{color:var(--dim);font-size:clamp(.74rem,1.4vw,.9rem);margin-top:12px;max-width:620px;line-height:1.6}}
.count{{text-align:right}}
.count .n{{font-family:'Orbitron',sans-serif;font-weight:900;font-size:clamp(2rem,5vw,3.6rem);color:var(--gold);line-height:1}}
.count .l{{font-size:.62rem;letter-spacing:.2em;text-transform:uppercase;color:var(--mut);margin-top:6px}}
.count .t{{font-size:.66rem;color:var(--mut);margin-top:8px}}
.stage{{position:relative;margin-top:8px;border:1px solid var(--line);border-radius:18px;overflow:hidden;
 background:rgba(8,7,4,.5);backdrop-filter:blur(8px)}}
.stage svg{{display:block;width:100%;height:auto}}
.node:hover circle:first-child{{stroke-width:3}}
.node.sel circle:first-child{{stroke-width:3;stroke:#fff}}
.core{{font-family:'Orbitron',sans-serif}}
.panel{{margin-top:16px;display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media(max-width:820px){{.panel{{grid-template-columns:1fr}}}}
.card{{border:1px solid var(--line);border-radius:14px;padding:16px 18px;background:rgba(10,9,5,.72);
 transition:transform .3s,box-shadow .3s}}
.card:hover{{transform:translateY(-3px);box-shadow:0 18px 50px rgba(0,0,0,.55)}}
.card h3{{font-family:'Orbitron',sans-serif;font-size:.8rem;letter-spacing:.14em;color:var(--gold);margin-bottom:10px}}
.kv{{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px dashed var(--line);font-size:.76rem}}
.kv:last-child{{border-bottom:0}}
.kv .k{{color:var(--mut)}} .kv .v{{color:var(--gold);text-align:right;word-break:break-all}}
.v.ok{{color:var(--neon)}} .v.bad{{color:var(--red)}}
pre.det{{background:rgba(0,0,0,.6);border:1px solid var(--line);border-radius:10px;padding:12px 14px;
 font-size:.68rem;color:#ffd966;white-space:pre-wrap;word-break:break-all;max-height:340px;overflow:auto;line-height:1.6}}
.lg{{display:inline-flex;align-items:center;gap:6px;font-size:.66rem;color:var(--mut);letter-spacing:.06em}}
.lg i{{width:8px;height:8px;border-radius:50%;display:inline-block}}
.legend{{display:flex;gap:14px;flex-wrap:wrap;margin-top:14px}}
footer{{margin-top:26px;padding-top:16px;border-top:1px solid var(--line);font-size:.7rem;color:var(--dim);
 display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}}
footer a{{color:var(--gold);text-decoration:none}}
#ae-qr-badge{{width:58px;height:58px;border-radius:12px;
 border:1px solid var(--gold);background:var(--void);padding:4px;display:block;text-decoration:none;
 box-shadow:0 8px 30px rgba(0,0,0,.6);transition:transform .3s,box-shadow .3s;flex:0 0 auto}}
#ae-qr-badge:hover{{transform:scale(1.12) rotate(-2deg);box-shadow:0 0 30px rgba(212,175,55,.55)}}
#ae-qr-badge img{{width:100%;height:100%;display:block;border-radius:8px}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.55}}}}
.live{{display:inline-flex;align-items:center;gap:7px;font-size:.62rem;letter-spacing:.18em;color:var(--neon);
 border:1px solid rgba(57,255,20,.35);padding:7px 12px;border-radius:999px;margin-top:12px}}
.live i{{width:6px;height:6px;border-radius:50%;background:var(--neon);animation:pulse 1.8s infinite}}
@media(prefers-reduced-motion:reduce){{*{{animation-duration:.01ms!important;transition-duration:.01ms!important}}}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <div class="eyebrow">æ:// tiny* · la familia soberana</div>
      <h1>tiny*</h1>
      <p class="sub">{len(FAMILY)} instrumentos, uno por capacidad. Cada nodo corrio su <b>doctor real</b> en esta maquina: el anillo dorado es una medicion, el rojo es una negativa. Haz click en un nodo para ver su recibo.</p>
      <div class="live"><i></i>MEDIDO · NO DECLARADO</div>
    </div>
    <div class="count">
      <div class="n">{total_ok}<span style="font-size:.45em;color:var(--mut)">/{len(FAMILY)}</span></div>
      <div class="l">doctors ejecutados</div>
      <div class="t">en {elapsed:.0f}s</div>
    </div>
  </header>

  <div class="stage">
    <svg viewBox="0 0 {W} {H}" role="img" aria-label="constelacion de la familia tiny*">
      {''.join(lines)}
      <circle cx="{W/2}" cy="{H/2}" r="86" fill="none" stroke="rgba(212,175,55,.28)" stroke-width="1"/>
      <circle cx="{W/2}" cy="{H/2}" r="70" fill="rgba(5,5,5,.8)" stroke="rgba(212,175,55,.45)"/>
      <text x="{W/2}" y="{H/2-6}" text-anchor="middle" fill="#D4AF37" font-size="26"
            font-family="Orbitron,sans-serif" font-weight="900">tiny*</text>
      <text x="{W/2}" y="{H/2+18}" text-anchor="middle" fill="#8a7a4a" font-size="11"
            font-family="JetBrains Mono,monospace">{len(FAMILY)} instrumentos</text>
      {''.join(nodes)}
    </svg>
  </div>

  <div class="legend">{''.join(legend)}</div>

  <div class="panel">
    <div class="card">
      <h3>DETALLE DEL NODO</h3>
      <div id="detail-empty" class="kv"><span class="k">selecciona un nodo de la constelacion</span><span class="v">—</span></div>
      {''.join(detail)}
    </div>
    <div class="card">
      <h3>LA FAMILIA</h3>
      <div id="family-list"></div>
    </div>
  </div>

  <footer>
    <span>tiny* · generado por <code style="background:rgba(0,0,0,.6);padding:.15rem .4rem;border-radius:4px;color:#ffd966">tiny_family.py</code> · cada doctor ejecutado en esta maquina.</span>
    <span style="display:flex;align-items:center;gap:14px">
      <span><a href="https://myaelmendez.github.io/tinyffmpeg.html">tinyffmpeg</a> · <a href="https://myaelmendez.github.io/aipodcast_me/skills-demo.html">demo de skills</a> · <a href="https://github.com/MYaelMendez">MYaelMendez</a></span>
      <a id="ae-qr-badge" href="https://myaelmendez.github.io/verify.html?url=https%3A%2F%2Fmyaelmendez.github.io%2Ftiny.html" target="_blank" rel="noopener" aria-label="Verify this surface">
        <img src="https://api.qrserver.com/v1/create-qr-code/?size=56x56&amp;data=https%3A%2F%2Fmyaelmendez.github.io%2Ftiny.html&amp;bgcolor=050505&amp;color=D4AF37" alt="QR verify" width="56" height="56">
      </a>
    </span>
  </footer>

<script>
const RESULTS = {payload};
const FAMILY = {json.dumps([f[0] for f in FAMILY])};
const list = document.getElementById('family-list');
FAMILY.forEach((n, i) => {{
  const r = RESULTS[i] || {{}};
  const ok = !!r.ok;
  const row = document.createElement('div');
  row.className = 'kv';
  row.innerHTML = '<span class="k">' + n + '</span><span class="v ' + (ok ? 'ok' : 'bad') + '">' +
                  (ok ? 'ok' : (r.refusal || 'REFUSED').slice(0, 42)) + ' · ' + (r._elapsed_s ?? '?') + 's</span>';
  row.style.cursor = 'pointer';
  row.onclick = () => select(n);
  list.appendChild(row);
}});

function select(name) {{
  document.querySelectorAll('.det').forEach(e => e.hidden = true);
  const d = document.getElementById('det-' + name);
  const empty = document.getElementById('detail-empty');
  if (d) {{ d.hidden = false; empty.hidden = true; }}
  else {{ empty.hidden = false; }}
  document.querySelectorAll('.node').forEach(g =>
    g.classList.toggle('sel', g.dataset.name === name));
}}
document.querySelectorAll('.node').forEach(g =>
  g.addEventListener('click', () => select(g.dataset.name)));
</script>
</body>
</html>
"""


def main() -> int:
    t0 = time.time()
    results = []
    for name, _, _ in FAMILY:
        r = run_doctor(name)
        results.append(r)
        print(f"  {name:<18} ok={r.get('ok')} {r.get('_elapsed_s')}s")
    elapsed = time.time() - t0
    ok = sum(1 for r in results if r.get("ok"))
    html = render(results, ok, elapsed)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"\ntiny* family -> {OUT}  {len(html.encode()):,} bytes · {ok}/{len(FAMILY)} ok en {elapsed:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
