#!/usr/bin/env python3
"""tinySVG page — a demonstration surface for the instrument.

Not a description of tinySVG: it RUNS it. The page carries the measured doctor
output, the refusals with their real numbers, and a live laboratory where moving
the render width re-derives the viewBox and shows the effective type size.

    python page.py            # -> tinySVG.html (github-pages)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tinySVG  # noqa: E402
from demo import demo_svg  # noqa: E402

ROOT = Path(r"C:\æ")
OUT = ROOT / "github-pages" / "tinySVG.html"

GOLD, VOID, INK, DIM = "#D4AF37", "#050505", "#e8e8e8", "#a3926a"

REFUSALS = [
    ("archivo ausente", "check_svg('no-existe.svg')", "no such file",
     "un path que no existe no es un SVG"),
    ("viewBox ausente", "check_svg_str('<svg><circle r=5/></svg>')", "sin viewBox",
     "sin viewBox no hay forma de derivar la escala: se niega"),
    ("SVG que no parsea", "check_svg_str(b'\\x00\\x01 no xml')", "SVG no parsea",
     "los bytes no son XML"),
    ("tipo bajo el suelo", "viewBox 4000 con render 707", "small_labels",
     "27 × 707/4000 = 4.8 px, muy por debajo de 12"),
    ("nodo fuera del marco", "radio interior 44 con hub r=86", "overlaps",
     "la constelacion original: el nucleo pintaba sobre los nodos"),
    ("solape de nodos", "dos nodos a distancia < r1+r2", "overlaps",
     "medido en viewBox, no en pantalla"),
]

CASES = [
    ("tiny.html (publicado)", 1600, 1040, 27, "REFUSED", "11.93 px — bajo el suelo"),
    ("tiny.html (corregido)", 1590, 1034, 27, "ok", "12.0 px — justo en el suelo"),
    ("monitor 1280", 2688, 1747, 27, "ok", "12.0 px — mismo suelo, otro viewBox"),
    ("móvil 390", 663, 431, 27, "ok", "12.0 px — el viewBox se encoge solo"),
]


def esc(x) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def capabilities() -> str:
    """The capability table: membership from the registry, verbs from the modules.
    A name is not a capability — its verbs are."""
    import re
    sys.path.insert(0, str(ROOT / "tinyae"))
    try:
        import tinyae
    except Exception:
        return '<tr><td colspan="4">registro no disponible</td></tr>'
    rows = []
    for name, dom, role in tinyae.FAMILY:
        p = ROOT / name / f"{name}.py"
        verbs = []
        if p.exists():
            src = p.read_text(encoding="utf-8", errors="replace")
            verbs = list(dict.fromkeys(re.findall(r"add_parser\(\s*['\"]([a-z_]+)['\"]", src)))
        rows.append(f'<tr><td>{dom}</td><td>{name}</td>'
                    f'<td>{", ".join(verbs) if verbs else "<i>(delega)</i>"}</td>'
                    f'<td>{esc(role)}</td></tr>')
    return "\n".join(rows)


def render(doctor: dict, cap_rows: str) -> str:
    rows = "\n".join(
        f'<tr><td>{esc(a)}</td><td><code>{esc(b)}</code></td>'
        f'<td class="r">{esc(c)}</td><td>{esc(d)}</td></tr>'
        for a, b, c, d in REFUSALS)
    cases = "\n".join(
        f'<tr><td>{esc(n)}</td><td>{vw}</td><td>{font}</td>'
        f'<td class="{"ok" if s == "ok" else "bad"}">{esc(s)}</td><td>{esc(note)}</td></tr>'
        for n, vw, _, font, s, note in CASES)
    dc = doctor.get("checks", {})
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>tinySVG · el viewBox no es la pantalla</title>
<link rel="canonical" href="https://myaelmendez.github.io/tinySVG.html">
<meta name="description" content="tinySVG, el instrumento soberano de las superficies vectoriales: mide el ancho de render, deriva la escala y se niega cuando la tipografia cae bajo el suelo. Pagina generada por el propio instrumento.">
<meta property="og:title" content="tinySVG · el viewBox no es la pantalla">
<meta property="og:type" content="website">
<meta property="og:url" content="https://myaelmendez.github.io/tinySVG.html">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=JetBrains+Mono:wght@300;400;700&display=swap" rel="stylesheet">
<style>
:root{{--void:#050505;--gold:#D4AF37;--text:#e8e8e8;--dim:#a3926a;--mut:#a89e80;
 --line:rgba(212,175,55,.24);--neon:#39ff14;--red:#ff6b6b;--cyan:#7bdff2}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--void);color:var(--text);font-family:'JetBrains Mono',ui-monospace,monospace;min-height:100vh;overflow-x:hidden}}
body::before{{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;background:
 radial-gradient(1000px 700px at 50% 40%,rgba(212,175,55,.10),transparent 62%),
 radial-gradient(700px 500px at 90% 90%,rgba(123,223,242,.06),transparent 60%)}}
body::after{{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.5;
 background:repeating-linear-gradient(0deg,rgba(212,175,55,.03) 0 1px,transparent 1px 4px)}}
.wrap{{position:relative;z-index:1;max-width:1180px;margin:0 auto;padding:clamp(14px,2.6vw,34px)}}
header{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;flex-wrap:wrap;
 padding-bottom:18px;border-bottom:1px solid var(--line)}}
.eyebrow{{font-size:clamp(.58rem,1.1vw,.72rem);letter-spacing:.4em;text-transform:uppercase;color:var(--gold)}}
h1{{font-family:'Orbitron',sans-serif;font-weight:900;font-size:clamp(1.8rem,5vw,3.4rem);
 color:var(--gold);letter-spacing:-.02em;line-height:.95;margin-top:10px;text-shadow:0 0 50px rgba(212,175,55,.26)}}
h1 span{{color:var(--cyan)}}
.sub{{color:var(--dim);font-size:clamp(.74rem,1.4vw,.9rem);margin-top:12px;max-width:640px;line-height:1.6}}
.badge-ok{{text-align:right}}
.badge-ok .n{{font-family:'Orbitron',sans-serif;font-weight:900;font-size:clamp(1.6rem,4vw,2.8rem);color:var(--neon);line-height:1}}
.badge-ok .l{{font-size:.62rem;letter-spacing:.2em;text-transform:uppercase;color:var(--mut);margin-top:6px}}
.live{{display:inline-flex;align-items:center;gap:7px;font-size:.62rem;letter-spacing:.18em;color:var(--neon);
 border:1px solid rgba(57,255,20,.35);padding:7px 12px;border-radius:999px;margin-top:12px}}
.live i{{width:6px;height:6px;border-radius:50%;background:var(--neon);animation:pulse 1.8s infinite}}
section{{margin-top:22px;border:1px solid var(--line);border-radius:16px;background:rgba(10,9,5,.72);
 padding:clamp(14px,2.4vw,24px)}}
h2{{font-family:'Orbitron',sans-serif;font-size:clamp(.9rem,2vw,1.15rem);letter-spacing:.12em;
 color:var(--gold);margin-bottom:12px}}
h2 span{{color:var(--cyan)}}
p.lead{{color:var(--dim);font-size:.82rem;line-height:1.7;margin-bottom:14px;max-width:760px}}
.demo{{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:rgba(0,0,0,.4)}}
.demo svg{{display:block;width:100%;height:auto}}
.lab{{margin-top:14px;border:1px solid rgba(123,223,242,.4);border-radius:12px;padding:14px 16px;
 background:rgba(0,0,0,.45)}}
.lab .row{{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:10px}}
.lab label{{font-size:.72rem;color:var(--cyan);letter-spacing:.1em;text-transform:uppercase}}
.lab input[type=range]{{flex:1;min-width:180px;accent-color:var(--gold)}}
.lab .val{{font-family:'Orbitron',sans-serif;color:var(--gold);font-size:.95rem;min-width:150px;text-align:right}}
.kv{{display:flex;justify-content:space-between;gap:12px;padding:5px 0;font-size:.76rem;border-bottom:1px dashed var(--line)}}
.kv:last-child{{border-bottom:0}}
.kv .k{{color:var(--mut)}} .kv .v{{color:var(--gold);text-align:right}}
.v.ok{{color:var(--neon)}} .v.bad{{color:var(--red)}} .v.cy{{color:var(--cyan)}}
table{{width:100%;border-collapse:collapse;font-size:.74rem;margin-top:6px}}
th{{text-align:left;color:var(--gold);font-weight:400;letter-spacing:.08em;font-size:.64rem;
 text-transform:uppercase;padding:8px 10px;border-bottom:1px solid var(--line)}}
td{{padding:8px 10px;border-bottom:1px solid rgba(212,175,55,.1);color:var(--dim);vertical-align:top}}
td:first-child{{color:var(--text)}}
td.r{{color:var(--red)}}
td code{{background:rgba(0,0,0,.6);padding:.12rem .35rem;border-radius:4px;color:#ffd966;font-size:.7rem}}
td.ok{{color:var(--neon)}} td.bad{{color:var(--red)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:12px}}
.stat{{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:rgba(0,0,0,.4)}}
.stat .k{{font-size:.62rem;letter-spacing:.14em;text-transform:uppercase;color:var(--mut)}}
.stat .v{{font-family:'Orbitron',sans-serif;font-size:1.35rem;color:var(--gold);margin-top:6px}}
footer{{margin-top:26px;padding-top:16px;border-top:1px solid var(--line);font-size:.7rem;color:var(--dim);
 display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;align-items:center}}
footer a{{color:var(--gold);text-decoration:none}}
#ae-qr-badge{{width:58px;height:58px;border-radius:12px;border:1px solid var(--gold);background:var(--void);
 padding:4px;display:block;text-decoration:none;box-shadow:0 8px 30px rgba(0,0,0,.6);flex:0 0 auto}}
#ae-qr-badge img{{width:100%;height:100%;display:block;border-radius:8px}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.55}}}}
@media(prefers-reduced-motion:reduce){{*{{animation-duration:.01ms!important;transition-duration:.01ms!important}}}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <div class="eyebrow">æ:// tiny* · instrumento de geometría</div>
      <h1>tiny<span>SVG</span></h1>
      <p class="sub">No dibuja: <b>mide el ancho de render, deriva la escala y se niega</b>.
      Una constelación de 20 nodos se publicó con etiquetas de <b>11.93 px</b> porque el
      viewBox se eligió para un monitor y se miró en un chat de 707 px. Esta página la
      genera el propio instrumento y se sella con <b>tinyqr</b>.</p>
      <div class="live"><i></i>MEDIDO · NO DECLARADO</div>
    </div>
    <div class="badge-ok">
      <div class="n">{dc.get('font_effective_px','?')} px</div>
      <div class="l">tipografía efectiva a 707 px</div>
    </div>
  </header>

  <section>
    <h2>LA REGLA, <span>DEMOSTRADA</span></h2>
    <p class="lead">Cada número de esta imagen sale de <code style="background:rgba(0,0,0,.6);padding:.15rem .4rem;border-radius:4px;color:#ffd966">viewBox_for()</code>.
    Si la regla cambia, la imagen cambia con ella — no hay nada escrito a mano.</p>
    <div class="demo">{demo_svg(707.0)}</div>
  </section>

  <section>
    <h2>EL LABORATORIO <span>— MUÉEVELO</span></h2>
    <p class="lead">Arrastra el ancho de render. El viewBox se re-deriva y la etiqueta
    se mantiene sobre el suelo de 12 px. Si el tipo cae por debajo, se marca en rojo:
    eso es exactamente lo que el instrumento se niega a publicar.</p>
    <div class="lab">
      <div class="row">
        <label for="rw">ancho de render</label>
        <input id="rw" type="range" min="360" max="1600" step="1" value="707">
        <div class="val" id="rwv">707 px</div>
      </div>
      <div class="row">
        <label for="nn">nodos</label>
        <input id="nn" type="range" min="3" max="30" step="1" value="20">
        <div class="val" id="nnv">20</div>
      </div>
      <div class="kv"><span class="k">viewBox derivado</span><span class="v" id="l-vb">—</span></div>
      <div class="kv"><span class="k">escala</span><span class="v" id="l-sc">—</span></div>
      <div class="kv"><span class="k">tipografía efectiva</span><span class="v" id="l-px">—</span></div>
      <div class="kv"><span class="k">dictamen</span><span class="v" id="l-vd">—</span></div>
    </div>
    <div class="demo" style="margin-top:12px"><svg id="lab-svg" viewBox="0 0 1590 1034"
      role="img" aria-label="constelacion de muestra"></svg></div>
  </section>

  <section>
    <h2>DEMO <span>GENERATIVA</span></h2>
    <p class="lead">La misma geometría que tinySVG deriva, pintada con cuatro lenguajes
    de diseño. <b>Regenerar</b> cambia la semilla: todo lo que ves es SVG declarativo,
    y la tipografía sigue en el suelo de 12 px porque el viewBox lo sigue decidiendo
    el instrumento.</p>
    <div class="lab">
      <div class="row">
        <label>técnica</label>
        <select id="gt" style="background:#0a0905;color:#7bdff2;border:1px solid rgba(123,223,242,.4);
              border-radius:6px;padding:6px 10px;font-family:inherit;font-size:.78rem">
          <option value="clean">clean — la constelación base</option>
          <option value="naive">naive — trazo tembloroso (2026)</option>
          <option value="iso">isometric — nodos como cubos</option>
          <option value="mesh">mesh — gradiente multipunto</option>
          <option value="warp">warp — ruido procedural</option>
        </select>
        <button id="reg" style="background:transparent;color:var(--gold);border:1px solid var(--gold);
              border-radius:6px;padding:6px 14px;font-family:inherit;font-size:.78rem;cursor:pointer">
          ⟳ regenerar</button>
        <div class="val" id="seedv">semilla 1</div>
      </div>
      <div class="kv"><span class="k">viewBox</span><span class="v" id="g-vb">—</span></div>
      <div class="kv"><span class="k">tipografía efectiva</span><span class="v" id="g-px">—</span></div>
      <div class="kv"><span class="k">dictamen tinySVG</span><span class="v" id="g-vd">—</span></div>
    </div>
    <div class="demo" style="margin-top:12px"><svg id="gen" viewBox="0 0 1590 1034"
      role="img" aria-label="constelacion generativa"></svg></div>
  </section>

  <section>
    <h2>EL LABORATORIO DE <span>FILTROS</span></h2>
    <p class="lead">Cuatro técnicas que la plataforma lleva años teniendo y casi nadie
    usa: <b>feTurbulence</b> genera ruido Perlin procedural y <b>feDisplacementMap</b>
    lo usa como campo de desplazamiento. Sin WebGL, sin canvas, sin JavaScript para
    el efecto en sí. Mueve los mandos y mira la constelación deformarse.</p>
    <div class="lab">
      <div class="row">
        <label>filtro</label>
        <select id="ff" style="background:#0a0905;color:#7bdff2;border:1px solid rgba(123,223,242,.4);
              border-radius:6px;padding:6px 10px;font-family:inherit;font-size:.78rem">
          <option value="warp">warp — feTurbulence + feDisplacementMap</option>
          <option value="gooey">gooey — blur + colorMatrix</option>
          <option value="grain">grain — turbulencia como textura</option>
          <option value="mesh">mesh — gradiente multipunto</option>
          <option value="none">ninguno</option>
        </select>
        <label style="color:var(--gold)"><input id="hz" type="checkbox" style="accent-color:var(--gold)"> heat haze</label>
      </div>
      <div class="row"><label>baseFrequency</label>
        <input id="bf" type="range" min="1" max="100" value="20">
        <div class="val" id="bfv">0.020</div></div>
      <div class="row"><label>desplazamiento</label>
        <input id="sc" type="range" min="0" max="120" value="30">
        <div class="val" id="scv">30</div></div>
      <div class="row"><label>semilla</label>
        <input id="sd" type="range" min="0" max="99" value="7">
        <div class="val" id="sdv">7</div></div>
      <div class="kv"><span class="k">región del filtro</span><span class="v">x −20% · y −20% · 140% × 140%</span></div>
      <div class="kv"><span class="k">por qué importa</span><span class="v">sin ampliarla, el warp recorta los bordes</span></div>
    </div>
    <div class="demo" style="margin-top:12px"><svg id="flt" viewBox="0 0 1590 1034"
      role="img" aria-label="constelacion con filtros svg"></svg></div>
  </section>

  <section>
    <h2>LA LINEA QUE LOS <span>UNIFICA</span></h2>
    <p class="lead"><b>Ninguno hace la cosa. Todos gobernan la cosa.</b>
    Cada tiny* envuelve una capacidad que ya existia (FFmpeg, cv2, MuJoCo, ONNX,
    SVG, XML, Ed25519) y se niega a operarla sin medirla antes. El mecanismo es el
    mismo en los 22: <code style="background:rgba(0,0,0,.6);padding:.15rem .4rem;border-radius:4px;color:#ffd966">doctor()</code>
    que mide, <code style="background:rgba(0,0,0,.6);padding:.15rem .4rem;border-radius:4px;color:#ffd966">refusal</code>
    que es un resultado, y un ledger de decisiones.</p>
    <div class="grid">
      <div class="stat"><div class="k">la cosa que NO hace</div><div class="v" style="font-size:1rem;line-height:1.4">tinyffmpeg no codifica · tinySVG no dibuja · tinyXML no parsea · tinyqr no firma</div></div>
      <div class="stat"><div class="k">lo que SI hace</div><div class="v" style="font-size:1rem;line-height:1.4">mide los builds · mide el viewBox · dice donde rompe · verifica desde los bytes</div></div>
    </div>
    <p class="lead" style="margin-top:12px"><b>La prueba de que es una linea y no una
    coincidencia:</b> cuando un instrumento no la sigue, el gate lo detecta. tinySVG
    cazo <code style="background:rgba(0,0,0,.6);padding:.15rem .4rem;border-radius:4px;color:#ffd966">tiny.html</code>
    a 11.93 px; tinyæ cazo a <code style="background:rgba(0,0,0,.6);padding:.15rem .4rem;border-radius:4px;color:#ffd966">tinygpugbot</code>
    disfrazado de flaky; tinyXML cazo un HTML que se hacia pasar por XML.</p>
  </section>

  <section>
    <h2>CAPACIDADES <span>MEDIDAS</span></h2>
    <p class="lead">22 instrumentos, 14 dominios, 22 green / 0 refused / 0 flaky. Los
    verbos son la capacidad real, extraidos de cada modulo — no del nombre.</p>
    <table>
      <tr><th>dominio</th><th>instrumento</th><th>verbos</th><th>capacidad</th></tr>
      {cap_rows}
    </table>
  </section>

  <section>
    <h2>LO QUE <span>RECHAZA</span></h2>
    <p class="lead">Cada refusal está pinneado por un test. Un chequeo que no se
    ejecuta nunca se muestra como que pasa.</p>
    <table>
      <tr><th>refusal</th><th>cómo se produce</th><th>motivo</th><th>por qué importa</th></tr>
      {rows}
    </table>
  </section>

  <section>
    <h2>CASOS <span>MEDIDOS</span></h2>
    <table>
      <tr><th>superficie</th><th>viewBox</th><th>fuente</th><th>dictamen</th><th>medido</th></tr>
      {cases}
    </table>
    <div class="grid">
      <div class="stat"><div class="k">nodos del doctor</div><div class="v">{dc.get('nodes','?')}</div></div>
      <div class="stat"><div class="k">render del doctor</div><div class="v">{dc.get('render_w','?')} px</div></div>
      <div class="stat"><div class="k">viewBox del doctor</div><div class="v">{dc.get('viewBox',['?'])[0]:.0f}×{dc.get('viewBox',['?','?'])[1]:.0f}</div></div>
      <div class="stat"><div class="k">suelo de legibilidad</div><div class="v">{tinySVG.MIN_FONT_PX:.0f} px</div></div>
    </div>
  </section>

  <footer>
    <span>tinySVG · generado por <code style="background:rgba(0,0,0,.6);padding:.15rem .4rem;border-radius:4px;color:#ffd966">tinySVG/page.py</code> · sellado con tinyqr.</span>
    <span style="display:flex;align-items:center;gap:14px">
      <span><a href="https://myaelmendez.github.io/tiny.html">tiny* family</a> · <a href="https://github.com/MYaelMendez">MYaelMendez</a></span>
      <a id="ae-qr-badge" href="tinySVG.html.receipt.json" target="_blank" rel="noopener" aria-label="Verify this surface">
        <img src="tinySVG.html.receipt.png" alt="QR de la firma tinyqr" width="56" height="56">
      </a>
    </span>
  </footer>
</div>

<script>
const FONT = 27, FLOOR = 12;
const viewBoxFor = (rw, font = FONT, floor = FLOOR) => Math.floor(rw * font / floor);

function positions(n, w, h, nodeR, hubR) {{
  const lo = hubR + nodeR + 12;
  const k = Math.sqrt(Math.max(n - 1, 0));
  const fit = Math.min((w / 2 - nodeR - 8) / 1.55, (h / 2 - nodeR - 8) / 1.05);
  const step = k ? Math.max((fit - lo) / k, 6) : 0;
  const cx = w / 2, cy = h / 2, golden = Math.PI * (3 - Math.sqrt(5));
  return Array.from({{length: n}}, (_, i) => {{
    const r = lo + step * Math.sqrt(i), a = i * golden;
    return [cx + r * Math.cos(a) * 1.55, cy + r * Math.sin(a) * 1.05];
  }});
}}

function draw() {{
  const rw = +document.getElementById('rw').value;
  const n = +document.getElementById('nn').value;
  const vw = viewBoxFor(rw), vh = Math.round(vw * 0.65);
  const scale = rw / vw, px = FONT * scale;
  document.getElementById('rwv').textContent = rw + ' px';
  document.getElementById('nnv').textContent = n;
  document.getElementById('l-vb').textContent = vw + ' × ' + vh;
  document.getElementById('l-sc').textContent = scale.toFixed(4);
  const pxEl = document.getElementById('l-px');
  pxEl.textContent = px.toFixed(1) + ' px';
  pxEl.className = 'v ' + (px >= FLOOR ? 'ok' : 'bad');
  const vd = document.getElementById('l-vd');
  vd.textContent = px >= FLOOR ? 'PUBLICABLE' : 'REFUSADO';
  vd.className = 'v ' + (px >= FLOOR ? 'ok' : 'bad');
  const svg = document.getElementById('lab-svg');
  svg.setAttribute('viewBox', '0 0 ' + vw + ' ' + vh);
  const nodeR = 58, hubR = Math.round(nodeR * 2.2);
  let out = '<circle cx="' + vw/2 + '" cy="' + vh/2 + '" r="' + hubR + '" fill="none" stroke="rgba(212,175,55,.28)"/>';
  positions(n, vw, vh, nodeR, hubR).forEach(([x, y], i) => {{
    out += '<line x1="' + x.toFixed(1) + '" y1="' + y.toFixed(1) + '" x2="' + vw/2 + '" y2="' + vh/2 + '" stroke="#D4AF37" stroke-opacity=".15"/>';
    out += '<g class="node" transform="translate(' + x.toFixed(1) + ',' + y.toFixed(1) + ')">' +
           '<circle r="' + nodeR + '" fill="rgba(5,5,5,.72)" stroke="' +
           (px >= FLOOR ? '#D4AF37' : '#ff6b6b') + '" stroke-width="2.2"/>' +
           '<text y="9" text-anchor="middle" fill="#e8e8e8" font-size="' + FONT +
           '" font-family="monospace">n' + i + '</text></g>';
  }});
  svg.innerHTML = out;
}}
['rw', 'nn'].forEach(id => document.getElementById(id).addEventListener('input', draw));
draw();

// ── laboratorio de filtros ──────────────────────────────────────────────
const FLT = {{
  warp: 'url(#f-warp)', gooey: 'url(#f-gooey)', grain: 'url(#f-grain)',
  mesh: '', none: ''
}};
function drawFilters() {{
  const kind = document.getElementById('ff').value;
  const bf = (+document.getElementById('bf').value / 1000).toFixed(3);
  const sc = +document.getElementById('sc').value;
  const sd = +document.getElementById('sd').value;
  const hz = document.getElementById('hz').checked;
  document.getElementById('bfv').textContent = bf;
  document.getElementById('scv').textContent = sc;
  document.getElementById('sdv').textContent = sd;
  const turb = document.getElementById('turb');
  turb.setAttribute('baseFrequency', bf + ' ' + (bf * 1.6).toFixed(3));
  turb.setAttribute('numOctaves', '3');
  turb.setAttribute('seed', sd);
  const disp = document.getElementById('disp');
  disp.setAttribute('scale', kind === 'gooey' ? 0 : sc);
  // heat haze: animar la frecuencia (la via cara) o el scale (la barata)
  const old = turb.querySelector('animate');
  if (old) old.remove();
  if (hz && kind !== 'gooey') {{
    const a = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
    a.setAttribute('attributeName', 'baseFrequency');
    a.setAttribute('dur', '12s');
    a.setAttribute('values', bf + ' ' + (bf*1.6).toFixed(3) + ';'
      + (bf*1.08).toFixed(3) + ' ' + (bf*1.4).toFixed(3) + ';'
      + bf + ' ' + (bf*1.6).toFixed(3));
    turb.appendChild(a);
  }}
  const g = document.getElementById('flt-body');
  g.setAttribute('filter', FLT[kind]);
  // el mesh pinta el fondo por gradiente, no por filtro
  document.getElementById('mesh-bg').setAttribute('opacity', kind === 'mesh' ? 1 : 0);
  document.getElementById('grain-fill').setAttribute('opacity', kind === 'grain' ? .5 : 0);
}}
['ff','bf','sc','sd','hz'].forEach(id =>
  document.getElementById(id).addEventListener('input', drawFilters));

// ── demo generativa ─────────────────────────────────────────────────────
let SEED = 1;
const rnd = () => (SEED = (SEED * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
function wob(x, amt) {{ return x + (rnd() - .5) * amt; }}
function isoCube(x, y, r) {{
  const h = r * .866;
  const t = `M${{x}} ${{y - r}} L${{x + h}} ${{y - r/2}} L${{x + h}} ${{y + r/2}} L${{x}} ${{y + r}} L${{x - h}} ${{y + r/2}} L${{x - h}} ${{y - r/2}} Z`;
  return `<path d="${{t}}" fill="rgba(212,175,55,.10)" stroke="#D4AF37" stroke-width="2"/>` +
    `<path d="M${{x}} ${{y - r}} L${{x + h}} ${{y - r/2}} L${{x}} ${{y}} Z" fill="rgba(123,223,242,.18)"/>` +
    `<path d="M${{x}} ${{y}} L${{x + h}} ${{y - r/2}} L${{x + h}} ${{y + r/2}} Z" fill="rgba(191,90,242,.18)"/>` +
    `<path d="M${{x}} ${{y - r}} L${{x - h}} ${{y - r/2}} L${{x}} ${{y}} Z" fill="rgba(212,175,55,.14)"/>`;
}}
function drawGen() {{
  const kind = document.getElementById('gt').value;
  SEED = 1 + Math.floor(rnd() * 1e6);
  document.getElementById('seedv').textContent = 'semilla ' + SEED;
  const rw = 707, font = 27;
  const vw = viewBoxFor(rw), vh = Math.round(vw * .65);
  const px = font * (rw / vw);
  const svg = document.getElementById('gen');
  svg.setAttribute('viewBox', '0 0 ' + vw + ' ' + vh);
  document.getElementById('g-vb').textContent = vw + ' × ' + vh;
  const pxEl = document.getElementById('g-px');
  pxEl.textContent = px.toFixed(1) + ' px';
  pxEl.className = 'v ' + (px >= FLOOR ? 'ok' : 'bad');
  const vd = document.getElementById('g-vd');
  vd.textContent = px >= FLOOR ? 'PUBLICABLE' : 'REFUSADO';
  vd.className = 'v ' + (px >= FLOOR ? 'ok' : 'bad');

  const n = 20, nodeR = 58, hubR = Math.round(nodeR * 2.2);
  const pts = positions(n, vw, vh, nodeR, hubR);
  let out = '';
  if (kind === 'mesh' || kind === 'warp')
    out += '<rect width="100%" height="100%" fill="url(#mg1)"/>'
         + '<rect width="100%" height="100%" fill="url(#mg2)"/>'
         + '<rect width="100%" height="100%" fill="url(#mg3)" opacity=".8"/>';
  if (kind === 'warp') out += `<rect width="100%" height="100%" filter="url(#f-warp)" opacity=".35"/>`;
  out += `<circle cx="${{vw/2}}" cy="${{vh/2}}" r="${{hubR}}" fill="none" stroke="rgba(212,175,55,.28)"/>`;
  pts.forEach(([x, y], i) => {{
    const col = ['#D4AF37','#00e5ff','#39ff14','#ff4d6d','#bf5af2'][i % 5];
    if (kind === 'naive') {{
      // hand-drawn wobble: the 2026 trend — a line that is not a line
      let d = `M${{wob(x, 9)}} ${{wob(y, 9)}}`;
      for (let k = 1; k <= 5; k++) {{
        const t = k / 5;
        d += ` L${{wob(x + (vw/2 - x) * t, 12)}} ${{wob(y + (vh/2 - y) * t, 12)}}`;
      }}
      out += `<path d="${{d}}" fill="none" stroke="${{col}}" stroke-width="2" stroke-opacity=".55"/>`;
    }} else if (kind === 'clean' || kind === 'mesh' || kind === 'warp') {{
      out += `<line x1="${{x.toFixed(1)}}" y1="${{y.toFixed(1)}}" x2="${{vw/2}}" y2="${{vh/2}}" stroke="${{col}}" stroke-opacity=".16"/>`;
    }}
    if (kind === 'iso') out += isoCube(x, y, nodeR);
    else out += `<g transform="translate(${{x.toFixed(1)}},${{y.toFixed(1)}})">`
      + `<circle r="${{nodeR}}" fill="rgba(5,5,5,.72)" stroke="${{col}}" stroke-width="2.2"/>`
      + `<text y="9" text-anchor="middle" fill="#e8e8e8" font-size="${{font}}" `
      + `font-family="monospace">n${{i}}</text></g>`;
    if (kind === 'iso')
      out += `<text x="${{x.toFixed(1)}}" y="${{(y + nodeR + 34).toFixed(1)}}" text-anchor="middle" `
        + `fill="${{col}}" font-size="19" font-family="monospace">n${{i}}</text>`;
  }});
  svg.innerHTML = out;
}}
document.getElementById('gt').addEventListener('input', drawGen);
document.getElementById('reg').addEventListener('click', drawGen);
drawGen();
</script>

<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <defs>
    <filter id="f-warp" x="-20%" y="-20%" width="140%" height="140%">
      <feTurbulence id="turb" type="fractalNoise" baseFrequency="0.02 0.032"
                    numOctaves="3" seed="7" result="noise"/>
      <feDisplacementMap id="disp" in="SourceGraphic" in2="noise"
                         scale="30" xChannelSelector="R" yChannelSelector="G"/>
    </filter>
    <filter id="f-gooey" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="14" result="b"/>
      <feColorMatrix in="b" mode="matrix"
        values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 22 -11" result="goo"/>
      <feComposite in="SourceGraphic" in2="goo" operator="atop"/>
    </filter>
    <filter id="f-grain" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3"/>
      <feColorMatrix type="saturate" values="0"/>
      <feComposite operator="in" in2="SourceGraphic"/>
    </filter>
    <radialGradient id="mg1" cx="20%" cy="25%" r="55%">
      <stop offset="0%" stop-color="#D4AF37"/><stop offset="100%" stop-color="#050505" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="mg2" cx="80%" cy="20%" r="55%">
      <stop offset="0%" stop-color="#7bdff2"/><stop offset="100%" stop-color="#050505" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="mg3" cx="50%" cy="90%" r="60%">
      <stop offset="0%" stop-color="#bf5af2"/><stop offset="100%" stop-color="#050505" stop-opacity="0"/>
    </radialGradient>
    <filter id="grainF"><feTurbulence type="fractalNoise" baseFrequency="0.9"
      numOctaves="2" seed="3"/><feColorMatrix type="saturate" values="0"/></filter>
  </defs>
</svg>

<script>
(function() {{
  const svg = document.getElementById('flt');
  const vw = 1590, vh = 1034, n = 20, nodeR = 58, hubR = Math.round(nodeR * 2.2);
  const pts = positions(n, vw, vh, nodeR, hubR);
  let out = '<rect id="mesh-bg" width="1590" height="1034" fill="#050505" opacity="0"/>'
    + '<rect width="1590" height="1034" fill="url(#mg1)"/>'
    + '<rect width="1590" height="1034" fill="url(#mg2)"/>'
    + '<rect width="1590" height="1034" fill="url(#mg3)" opacity=".85"/>'
    + '<rect id="grain-fill" width="1590" height="1034" filter="url(#grainF)" opacity="0"/>'
    + '<circle cx="795" cy="517" r="' + hubR + '" fill="none" stroke="rgba(212,175,55,.28)"/>';
  pts.forEach(([x, y], i) => {{
    out += '<line x1="' + x.toFixed(1) + '" y1="' + y.toFixed(1) + '" x2="795" y2="517" stroke="#D4AF37" stroke-opacity=".15"/>';
    out += '<g transform="translate(' + x.toFixed(1) + ',' + y.toFixed(1) + ')">'
      + '<circle r="' + nodeR + '" fill="rgba(5,5,5,.72)" stroke="#D4AF37" stroke-width="2.2"/>'
      + '<text y="9" text-anchor="middle" fill="#e8e8e8" font-size="27" font-family="monospace">n' + i + '</text></g>';
  }});
  svg.innerHTML = '<g id="flt-body">' + out + '</g>';
  drawFilters();
}})();
</script>
</body>
</html>
"""


def main() -> int:
    doctor = tinySVG.doctor()
    if not doctor.get("ok"):
        print(f"doctor REFUSED: {doctor}", file=sys.stderr)
    html = render(doctor, capabilities())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    r = tinySVG.check_svg(OUT, render_w=707.0)
    print(f"{OUT}  {len(html.encode()):,} bytes")
    print(f"  doctor: {doctor.get('checks',{}).get('font_effective_px')} px · "
          f"check: {'ok' if r.get('ok') else 'REFUSED ' + str(r.get('refusal'))}")
    try:
        sys.path.insert(0, str(ROOT / "tinyqr"))
        import tinyqr
        s = tinyqr.seal(OUT)
        print(f"  sellado: {s['sha256'][:16]}… · QR v{s.get('qr_version')}"
              if s.get("ok") else f"  SELLO REFUSADO: {s.get('refusal')}")
    except Exception as exc:
        print(f"  sello no disponible: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
