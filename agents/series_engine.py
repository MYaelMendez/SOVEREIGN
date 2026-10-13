#!/usr/bin/env python3
"""
series_engine.py — a series is a spec, not a scene.

THE PROBLEM
-----------
Every video so far has been a hand-written scene: ~500 lines of canvas code
each, all sharing the same skeleton (boot, acts, warm wash, HUD, frame hook).
Writing the next one meant copying the last one and editing 40 strings.

A SERIES IS DATA
----------------
The skeleton is the same every time. What changes is the content. So the
content becomes a JSON spec and the engine emits the scene:

    series.json  →  scene HTML  →  render  →  gate  →  deploy  →  æQR

Change the JSON, get a new episode. That is "content according to our needs".

WHAT THE ENGINE GUARANTEES (the defects this session kept finding)
------------------------------------------------------------------
  · the warm wash is ALWAYS emitted — gold on void #050505 is luminance 5 and
    the gate refuses a frame with no mass
  · no duplicate id attributes, and every getElementById target is emitted
  · classic canvas + inline script only (the producer rejects importmap/module)
  · the scene declares the spec's exact width/height
  · __renderFrame is always present and correct

Those are the four things that have cost renders. The engine makes them
impossible to forget rather than remembering them each time.

COMMANDS
    python series_engine.py check  <series.json>        # validate + report
    python series_engine.py emit   <series.json>        # write the scenes
    python series_engine.py render <series.json>        # emit + render + gate
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time

AE = pathlib.Path(os.environ.get("AE_ROOT", r"C:\æ"))
SCENES = AE / "site" / "aipodcast_me"
SPECS = AE / "studio" / "specs"
OUT = AE / "studio" / "output"
GPU = os.environ.get("AE_GPU_PYTHON", r"C:\gpu\Scripts\python.exe")
PY = os.environ.get("AE_PYTHON",
                    str(pathlib.Path(os.environ.get("LOCALAPPDATA", ""))
                        / "hermes" / "hermes-agent" / "venv" / "Scripts" / "python.exe"))

REQUIRED_SERIES = ("series", "brand", "episodes")
REQUIRED_EPISODE = ("id", "title", "subtitle", "acts")

# The scene skeleton. {…} slots are filled from the spec. The wash, the frame
# hook and the HUD are NOT optional and are not slots — they are always emitted.
TEMPLATE = r'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width={w},height={h}">
<title>{brand} — {title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Orbitron:wght@700;900&display=swap" rel="stylesheet">
<style>
:root{{--void:#050505;--gold:#D4AF37;--goldhi:#FFD700;--cyan:#00eaff;--neon:#00ff9d}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:var(--void);
  font-family:'JetBrains Mono',ui-monospace,monospace}}
#c{{position:fixed;top:0;left:0;width:{w}px;height:{h}px;display:block;z-index:1}}
#scanlines{{position:fixed;top:0;left:0;width:{w}px;height:{h}px;z-index:40;pointer-events:none;
  background:repeating-linear-gradient(0deg,rgba(0,0,0,0.20) 0px,rgba(0,0,0,0.20) 1px,transparent 1px,transparent 3px);
  mix-blend-mode:multiply}}
#vignette{{position:fixed;top:0;left:0;width:{w}px;height:{h}px;z-index:41;pointer-events:none;
  background:radial-gradient(ellipse at 50% 48%,transparent 66%,rgba(0,0,0,0.46) 100%)}}
#hud{{position:fixed;top:{hud_top}px;left:{pad}px;right:{pad}px;z-index:50;pointer-events:none}}
#hud .prompt{{font-size:{f_prompt}px;letter-spacing:7px;color:var(--goldhi);opacity:.95}}
#hud h1{{font-family:'Orbitron',sans-serif;font-size:{f_h1}px;font-weight:900;letter-spacing:1px;
  margin-top:18px;color:var(--goldhi);text-shadow:0 0 30px rgba(255,215,0,0.5);line-height:1.1}}
#hud .rule{{width:100%;height:1px;margin:24px 0;
  background:linear-gradient(90deg,var(--gold),rgba(212,175,55,0.05))}}
#hud .sub{{font-size:{f_sub}px;letter-spacing:3px;color:var(--cyan);text-transform:uppercase;opacity:.94}}
#pbar{{position:fixed;bottom:{pbar_b}px;left:{pad}px;right:{pad}px;z-index:50;height:12px;
  border:1px solid rgba(212,175,55,.55);border-radius:6px;overflow:hidden;
  background:rgba(212,175,55,0.07)}}
#pfill{{height:100%;width:0%;background:linear-gradient(90deg,#D4AF37,#00ff9d)}}
#tags{{position:fixed;bottom:{tags_b}px;left:{pad}px;right:{pad}px;z-index:50;
  font-size:{f_tags}px;letter-spacing:2px;color:var(--gold);opacity:.92}}
#readout{{position:fixed;bottom:{ro_b}px;left:{pad}px;z-index:50;color:var(--cyan);
  font-size:{f_ro}px;letter-spacing:3px}}
#readout .g{{color:var(--goldhi)}}
#ph{{position:fixed;bottom:{ro_b}px;right:{pad}px;z-index:50;color:var(--gold);
  font-size:{f_ro}px;letter-spacing:5px;text-transform:uppercase;opacity:.9}}
</style>
</head>
<body>
<canvas id="c" width="{w}" height="{h}"></canvas>
<div id="scanlines"></div>
<div id="vignette"></div>

<div id="hud">
  <div class="prompt">&gt;_{prompt}</div>
  <h1 id="ttl">{title}</h1>
  <div class="rule"></div>
  <div class="sub" id="stl">{subtitle}</div>
</div>
<div id="pbar"><div id="pfill"></div></div>
<div id="tags">{tags}</div>
<div id="readout">frame <span class="g" id="fc">0</span> / <span id="tc">0</span> &middot; t <span class="g" id="tt">0.00</span>s</div>
<div id="ph">{first_phase}</div>

<script>
/* ============================================================
   {brand} — {title}
   GENERATED by series_engine.py from {series}.json — do not hand-edit.
   Episode id: {id}
   {w}x{h} · Canvas 2D only (the producer rejects importmap/module).

   The warm wash below is not decoration: gold on void #050505 is luminance 5
   and the gate refuses a frame with no mass.
   ============================================================ */
const W = {w}, H = {h}, DURATION = {duration};
const cv = document.getElementById('c');
const cx = cv.getContext('2d', {{ alpha: false }});

const GOLD = '#D4AF37', GOLDHI = '#FFD700', CYAN = '#00eaff', NEON = '#00ff9d';
const TXT = '#F2EFE6', RED = '#ff6b6b';

function mulberry32(a){{return function(){{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);
  t^=t>>>7;t=Math.imul(t,61|t)^t;return((t^t>>>14)>>>0)/4294967296;}};}}
const clamp = (v,a,b) => v < a ? a : v > b ? b : v;
const ease  = x => x < 0.5 ? 2*x*x : 1 - Math.pow(-2*x+2, 2)/2;
const seg   = (t,a,b) => clamp((t-a)/(b-a), 0, 1);
const pulse = (t,s) => 0.5 + 0.5*Math.sin(t*s);

const ACTS = {acts_json};
const PHASES = {phases_json};
const TITLES = {titles_json};

function bg(t){{
  cx.fillStyle = '#050505'; cx.fillRect(0,0,W,H);
  const wash = cx.createRadialGradient(W*0.5, H*0.46, 0, W*0.5, H*0.46, H*0.62);
  wash.addColorStop(0.00, 'rgba(60,52,35,0.95)');
  wash.addColorStop(0.55, 'rgba(43,37,25,0.86)');
  wash.addColorStop(1.00, 'rgba(12,11,8,0.52)');
  cx.fillStyle = wash; cx.fillRect(0,0,W,H);

  cx.strokeStyle = 'rgba(212,175,55,0.10)'; cx.lineWidth = 1;
  const off = (t*12) % 72;
  for (let x = -72 + off; x < W; x += 72){{ cx.beginPath(); cx.moveTo(x,0); cx.lineTo(x,H); cx.stroke(); }}
  for (let y = -72 + off; y < H; y += 72){{ cx.beginPath(); cx.moveTo(0,y); cx.lineTo(W,y); cx.stroke(); }}

  drawSwarm(t, 0.55);
}}

/* the act renderers — one per kind the spec may use */
function drawIntro(t, on, a){{
  if (on <= 0) return;
  const cxp = W/2, cyp = {cy_intro};
  cx.save(); cx.textAlign = 'center';
  cx.globalAlpha = ease(on) * ease(seg(t, 0.2, 0.9));
  const g = cx.createRadialGradient(cxp, cyp, 0, cxp, cyp, 340);
  g.addColorStop(0, 'rgba(255,215,0,' + (0.30*(0.7+0.3*pulse(t,2.4))) + ')');
  g.addColorStop(1, 'rgba(255,215,0,0)');
  cx.fillStyle = g; cx.beginPath(); cx.arc(cxp, cyp, 340, 0, 7); cx.fill();
  cx.fillStyle = GOLDHI;
  cx.font = '900 {f_big}px "Orbitron", sans-serif';
  cx.fillText(a.big, cxp, cyp + 10);
  let y = cyp + {gap_big};
  for (let i = 0; i < (a.lines||[]).length; i++){{
    cx.globalAlpha = ease(on) * ease(seg(t, 0.9 + i*0.45, 1.5 + i*0.45));
    const L = a.lines[i];
    cx.fillStyle = L[1] || TXT;
    cx.font = (L[2]||'400') + ' ' + (L[3]||26) + 'px "JetBrains Mono", monospace';
    cx.fillText(L[0], cxp, y); y += (L[4]||56);
  }}
  cx.restore();
}}

function drawList(t, on, a){{
  if (on <= 0) return;
  const per = ({span}) / Math.max(1,(a.items||[]).length);
  const first = Math.max(0, Math.floor((t - {a0}) / per) - 1);
  const items = a.items || [];
  cx.save();
  for (let i = first; i < Math.min(items.length, first + {rows}); i++){{
    const it = items[i];
    const at = {a0} + i * per;
    const ap = ease(seg(t, at, at + per*0.5));
    const y = {list_top} + (i - first) * {row_h};
    cx.globalAlpha = ease(on) * ap;
    cx.textAlign = 'right';
    cx.fillStyle = it[2] || GOLD;
    cx.font = '900 {f_key}px "Orbitron", sans-serif';
    cx.fillText(it[0], {key_x}, y + 10);
    cx.strokeStyle = 'rgba(212,175,55,0.30)'; cx.lineWidth = 1.4;
    cx.beginPath(); cx.moveTo({key_x}+26, y + 2); cx.lineTo({key_x}+60, y + 2); cx.stroke();
    cx.textAlign = 'left';
    cx.fillStyle = TXT;
    cx.font = '700 {f_item}px "JetBrains Mono", monospace';
    cx.fillText(it[1], {key_x}+86, y + 10);
  }}
  if (a.footer){{
    cx.textAlign = 'center';
    cx.globalAlpha = ease(on) * ease(seg(t, {foot_at}, {foot_at}+0.6));
    cx.fillStyle = GOLDHI;
    cx.font = '700 {f_foot}px "JetBrains Mono", monospace';
    cx.fillText(a.footer, W/2, {foot_y});
  }}
  cx.restore();
}}

function drawBlocks(t, on, a){{
  if (on <= 0) return;
  const items = a.items || [];
  cx.save(); cx.textAlign = 'center';
  const cxp = W/2;
  if (a.head){{
    cx.globalAlpha = ease(on) * ease(seg(t, {b0}-0.2, {b0}+0.4));
    cx.fillStyle = GOLDHI;
    cx.font = '900 {f_bhead}px "Orbitron", sans-serif';
    cx.fillText(a.head, cxp, {blocks_top}-{bhead_gap});
  }}
  for (let i = 0; i < items.length; i++){{
    const it = items[i];
    const at = {b0} + i*0.55;
    const ap = ease(seg(t, at, at + 0.45));
    const y = {blocks_top} + i*{block_h};
    cx.globalAlpha = ease(on) * ap;
    const bw = {block_w}, bh = {block_bh};
    cx.strokeStyle = 'rgba(212,175,55,' + (0.40*ap).toFixed(3) + ')';
    cx.lineWidth = 1.6;
    cx.strokeRect(cxp - bw/2, y - 36, bw, bh);
    cx.fillStyle = 'rgba(212,175,55,0.08)';
    cx.fillRect(cxp - bw/2, y - 36, bw, bh);
    cx.fillStyle = it[1] || (i===0?GOLDHI:(i===1?CYAN:NEON));
    cx.font = '900 {f_block}px "Orbitron", sans-serif';
    cx.fillText(it[0], cxp, y + 30);
    if (it[2]){{
      cx.fillStyle = CYAN;
      cx.font = '400 {f_block_sub}px "JetBrains Mono", monospace';
      cx.fillText(it[2], cxp, y + 68);
    }}
  }}
  if (a.closer){{
    cx.globalAlpha = ease(on) * ease(seg(t, {closer_at}, {closer_at}+0.6));
    cx.fillStyle = a.closer_color || TXT;
    cx.font = '700 {f_closer}px "JetBrains Mono", monospace';
    cx.fillText(a.closer, cxp, {closer_y});
  }}
  cx.restore();
}}

function drawOutro(t, on, a){{
  if (on <= 0) return;
  const cxp = W/2, cyp = {cy_outro};
  cx.save(); cx.textAlign = 'center';
  cx.globalAlpha = ease(on);
  const g = cx.createRadialGradient(cxp, cyp, 0, cxp, cyp, 400);
  g.addColorStop(0, 'rgba(255,215,0,0.22)');
  g.addColorStop(1, 'rgba(255,215,0,0)');
  cx.fillStyle = g; cx.beginPath(); cx.arc(cxp, cyp, 400, 0, 7); cx.fill();
  let y = cyp - 150;
  for (let i = 0; i < (a.lines||[]).length; i++){{
    const L = a.lines[i];
    cx.globalAlpha = ease(on) * ease(seg(t, {o0} + i*0.4, {o0}+0.4 + i*0.4));
    cx.fillStyle = L[1] || TXT;
    cx.font = (L[2]||'700') + ' ' + (L[3]||30) + 'px ' + (L[5]||'"JetBrains Mono", monospace');
    cx.fillText(L[0], cxp, y); y += (L[4]||60);
  }}
  cx.restore();
}}

/* ---- particle swarm: the æ:// texture ---- */
const SWARM = (() => {{
  const r = mulberry32(808), o = [];
  for (let i = 0; i < 46; i++) o.push({{
    x: r()*W, y: r()*H, ph: r()*Math.PI*2,
    r: 1.4 + r()*3.4, vx: (r()-.5)*18, vy: (r()-.5)*14, k: r(),
  }});
  return o;
}})();
function drawSwarm(t, alpha){{
  if (alpha <= 0) return;
  for (const p of SWARM){{
    p.x += p.vx * 0.016; p.y += p.vy * 0.016;
    if (p.x < -20) p.x = W+20; if (p.x > W+20) p.x = -20;
    if (p.y < -20) p.y = H+20; if (p.y > H+20) p.y = -20;
    const tw = 0.5 + 0.5*Math.sin(t*(1.2+p.k*2) + p.ph);
    cx.globalAlpha = alpha * (0.10 + 0.30*tw);
    cx.fillStyle = p.k < 0.22 ? GOLDHI : CYAN;
    cx.beginPath(); cx.arc(p.x, p.y, p.r, 0, 7); cx.fill();
    cx.globalAlpha = alpha * 0.05;
    cx.beginPath(); cx.arc(p.x, p.y, p.r*4, 0, 7); cx.fill();
  }}
  cx.globalAlpha = 1;
}}

/* ---- act 5: an event timeline ---- */
function drawTimeline(t, on, a){{
  if (on <= 0) return;
  cx.save(); cx.textAlign = 'center';
  const cxp = W/2;
  if (a.head){{
    cx.globalAlpha = ease(on) * ease(seg(t, {tl0}-0.25, {tl0}+0.4));
    cx.fillStyle = GOLDHI;
    cx.font = '900 {f_tlhead}px "Orbitron", sans-serif';
    cx.fillText(a.head, cxp, {tl_top}-{tlhead_gap});
  }}
  const items = a.items || [];
  const y = {tl_top} + {tl_rows}/2 - 24;
  const reach = ease(seg(t, {tl0}, {tl0}+0.9));
  cx.globalAlpha = ease(on) * reach;
  cx.strokeStyle = 'rgba(212,175,55,0.55)'; cx.lineWidth = 2.4;
  cx.beginPath(); cx.moveTo({tl_axis0}, y); cx.lineTo({tl_axis0} + ({tl_axis1}-{tl_axis0})*reach, y); cx.stroke();
  for (let i = 0; i < items.length; i++){{
    const it = items[i];
    const x = {tl_axis0} + ({tl_axis1}-{tl_axis0}) * (items.length === 1 ? 0.5 : i/(items.length-1));
    const at = {tl0} + 0.55 + i*0.34;
    const ap = ease(seg(t, at, at+0.34));
    const tw = 0.5 + 0.5*Math.sin(t*2 + i);
    cx.globalAlpha = ease(on) * ap * (0.55 + 0.45*tw);
    cx.fillStyle = GOLDHI;
    cx.beginPath(); cx.arc(x, y, 8, 0, 7); cx.fill();
    cx.globalAlpha = ease(on) * ap;
    cx.fillStyle = it[2] || GOLD;
    cx.font = '900 {f_tlkey}px "Orbitron", sans-serif';
    cx.textAlign = 'center';
    cx.fillText(it[0], x, y - 42);
    cx.fillStyle = TXT;
    cx.font = '700 {f_tlitem}px "JetBrains Mono", monospace';
    cx.fillText(it[1], x, y + 56);
  }}
  if (a.closer){{
    cx.globalAlpha = ease(on) * ease(seg(t, {tl_close}, {tl_close}+0.6));
    cx.fillStyle = a.closer_color || TXT;
    cx.font = '700 {f_tlcloser}px "JetBrains Mono", monospace';
    cx.fillText(a.closer, cxp, {tl_close_y});
  }}
  cx.restore();
}}

/* ---- act 6: A/B comparison ---- */
function drawCompare(t, on, a){{
  if (on <= 0) return;
  const items = a.items || [];
  if (items.length < 2) return;
  cx.save(); cx.textAlign = 'center';
  const half = {cmp_w};
  const x0 = {cmp_x};
  for (let i = 0; i < 2; i++){{
    const it = items[i];
    const at = {cmp0} + i*0.55;
    const ap = ease(seg(t, at, at+0.45));
    const x = x0 + i*half + half/2;
    cx.globalAlpha = ease(on) * ap;
    cx.strokeStyle = i === 0 ? 'rgba(255,215,0,' + (0.42*ap).toFixed(3) + ')' : 'rgba(0,255,157,' + (0.42*ap).toFixed(3) + ')';
    cx.lineWidth = 1.8;
    cx.strokeRect(x - half/2 + 24, {cmp_top} - 24, half - 48, {cmp_h});
    cx.fillStyle = i === 0 ? 'rgba(255,215,0,0.08)' : 'rgba(0,255,157,0.08)';
    cx.fillRect(x - half/2 + 24, {cmp_top} - 24, half - 48, {cmp_h});
    cx.fillStyle = i === 0 ? GOLDHI : NEON;
    cx.font = '900 {f_cmp}px "Orbitron", sans-serif';
    cx.fillText(it[0], x, {cmp_top} + 46);
    cx.fillStyle = CYAN;
    cx.font = '400 {f_cmp_sub}px "JetBrains Mono", monospace';
    cx.fillText(it[1], x, {cmp_top} + 92);
    if (it[2]){{
      cx.fillStyle = TXT;
      cx.font = '700 {f_cmp_body}px "JetBrains Mono", monospace';
      cx.fillText(it[2], x, {cmp_top} + 148);
    }}
    if (it[3]){{
      cx.fillStyle = GOLD;
      cx.font = '400 {f_cmp_small}px "JetBrains Mono", monospace';
      cx.fillText(it[3], x, {cmp_top} + 188);
    }}
  }}
  cx.globalAlpha = ease(on) * ease(seg(t, {cmp0}+0.4, {cmp0}+0.9));
  cx.fillStyle = TXT;
  cx.font = '900 {f_vs}px "Orbitron", sans-serif';
  cx.fillText('VS', x0 + half, {cmp_top} + {cmp_vs});
  if (a.closer){{
    cx.globalAlpha = ease(on) * ease(seg(t, {cmp_close}, {cmp_close}+0.6));
    cx.fillStyle = a.closer_color || TXT;
    cx.font = '700 {f_cmp_closer}px "JetBrains Mono", monospace';
    cx.fillText(a.closer, W/2, {cmp_close_y});
  }}
  cx.restore();
}}

const RENDERERS = {{ intro: drawIntro, list: drawList, blocks: drawBlocks, outro: drawOutro, timeline: drawTimeline, compare: drawCompare }};

function phaseAt(t){{
  const n = ACTS.length;
  const i = clamp(Math.floor(t / (DURATION/n)), 0, n-1);
  return PHASES[i] || PHASES[0];
}}
function titleAt(t){{
  const n = ACTS.length;
  const i = clamp(Math.floor(t / (DURATION/n)), 0, n-1);
  return TITLES[i] || TITLES[0];
}}

const ttlEl = document.getElementById('ttl');
const stlEl = document.getElementById('stl');
const phEl  = document.getElementById('ph');
const pfEl  = document.getElementById('pfill');
function hud(t){{
  const [ph, sub] = phaseAt(t);
  const ti = titleAt(t);
  if (ttlEl.textContent !== ti) ttlEl.textContent = ti;
  if (stlEl.textContent !== sub) stlEl.textContent = sub;
  if (phEl.textContent !== ph) phEl.textContent = ph;
  pfEl.style.width = ((t/DURATION)*100).toFixed(2) + '%';
}}

function renderAt(t){{
  t = clamp(t, 0, DURATION);
  bg(t);
  hud(t);
  const n = ACTS.length, span = DURATION/n;
  for (let i = 0; i < n; i++){{
    const a0 = i*span, a1 = a0 + span;
    const on = ease(seg(t, a0, a0 + span*0.15)) * (1 - ease(seg(t, a1 - span*0.15, a1)));
    const fn = RENDERERS[ACTS[i].kind];
    if (fn) fn(t, on, ACTS[i]);
  }}
}}

let driven = false;
window.__renderFrame = function (i, total){{
  driven = true;
  const n = Math.max(1, (total || 1) - 1);
  const t = (i / n) * DURATION;
  renderAt(t);
  document.getElementById('fc').textContent = i;
  document.getElementById('tc').textContent = total;
  document.getElementById('tt').textContent = t.toFixed(2);
  return true;
}};
function loop(){{
  if (!driven) renderAt((performance.now()/1000) % DURATION);
  requestAnimationFrame(loop);
}}
loop();
window.__renderFrame(0, 1);
</script>
</body>
</html>
'''


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(s: dict) -> list[str]:
    """Everything the engine must be able to promise, checked up front."""
    errs = []
    for k in REQUIRED_SERIES:
        if k not in s:
            errs.append(f"series missing '{k}'")
    if errs:
        return errs
    for e in s["episodes"]:
        for k in REQUIRED_EPISODE:
            if k not in e:
                errs.append(f"{e.get('id','?')}: missing '{k}'")
        for i, a in enumerate(e.get("acts", [])):
            if a.get("kind") not in ("intro", "list", "blocks", "outro", "timeline", "compare"):
                errs.append(f"{e.get('id','?')}: act {i} unknown kind {a.get('kind')!r}")
    return errs


def geometry(s: dict) -> dict:
    """The frame numbers, derived from the aspect so a 9:16 and a 16:9 both work."""
    w = s.get("width", 1080)
    h = s.get("height", 1920)
    v = h > w            # vertical?
    return {
        "w": w, "h": h,
        "pad": 72 if v else 54,
        "hud_top": 84 if v else 46,
        "f_prompt": 19 if v else 15,
        "f_h1": 42 if v else 38,
        "f_sub": 20 if v else 16,
        "f_tags": 19 if v else 15,
        "f_ro": 16 if v else 14,
        "pbar_b": 168 if v else 52,
        "tags_b": 106 if v else 26,
        "ro_b": 56 if v else 26,
        "cy_intro": int(h*0.485), "cy_outro": int(h*0.49),
        "f_big": 76 if v else 64,
        "gap_big": 106 if v else 88,
        "a0": 3.2, "span": 9.4,
        "rows": 9 if v else 7,
        "list_top": 420 if v else 300,
        "row_h": 128 if v else 96,
        "f_key": 34 if v else 28, "key_x": 250 if v else 210,
        "f_item": 29 if v else 24,
        "foot_at": 11.8, "foot_y": 1680 if v else 940,
        "f_foot": 27 if v else 23,
        "b0": 12.9, "blocks_top": 820 if v else 620,
        "block_h": 160 if v else 130,
        "block_w": 720 if v else 620, "block_bh": 112 if v else 96,
        "f_bhead": 52 if v else 44, "bhead_gap": 120,
        "f_block": 44 if v else 38, "f_block_sub": 21 if v else 19,
        "closer_at": 14.6, "closer_y": 1400 if v else 1000,
        "f_closer": 24 if v else 21,
        "o0": 0.6,
    }


def emit(s: dict, out_dir: pathlib.Path | None = None) -> list[dict]:
    out_dir = out_dir or SCENES
    out_dir.mkdir(parents=True, exist_ok=True)
    g = geometry(s)
    written = []
    for e in s["episodes"]:
        acts = e["acts"]
        n = len(acts)
        span = s.get("duration", 18) / max(1, n)
        ctx = dict(g)
        v = g["h"] > g["w"]
        # each act's own timing window
        ctx["span"] = round(span * 0.9, 3)
        ctx["b0"] = round(span*2 + 0.3, 3)
        ctx["closer_at"] = round(span*2 + 1.7, 3)
        ctx["o0"] = round(span*(n-1) + 0.6, 3)
        ctx["foot_at"] = round(span*1 + 8.6, 3)
        ctx["a0"] = round(span*1 + 0.2, 3)
        # timeline act
        ctx["tl0"] = round(span*2 + 0.3, 3)
        ctx["tl_top"] = 820 if v else 620
        ctx["tl_rows"] = 320 if v else 240
        ctx["tlhead_gap"] = 120
        ctx["f_tlhead"] = 50 if v else 42
        ctx["f_tlkey"] = 34 if v else 28
        ctx["f_tlitem"] = 24 if v else 21
        ctx["tl_axis0"] = 140 if v else 120
        ctx["tl_axis1"] = 940 if v else 960
        ctx["tl_close"] = round(span*2 + 2.4, 3)
        ctx["tl_close_y"] = 1400 if v else 1000
        ctx["f_tlcloser"] = 24 if v else 21
        # compare act
        ctx["cmp0"] = round(span*2 + 0.3, 3)
        ctx["cmp_w"] = 400 if v else 340
        ctx["cmp_x"] = 140 if v else 120
        ctx["cmp_top"] = 800 if v else 600
        ctx["cmp_h"] = 340 if v else 280
        ctx["f_cmp"] = 40 if v else 34
        ctx["f_cmp_sub"] = 22 if v else 19
        ctx["f_cmp_body"] = 26 if v else 22
        ctx["f_cmp_small"] = 20 if v else 18
        ctx["cmp_vs"] = 60
        ctx["f_vs"] = 52 if v else 44
        ctx["cmp_close"] = round(span*2 + 2.4, 3)
        ctx["cmp_close_y"] = 1400 if v else 1000
        ctx["f_cmp_closer"] = 24 if v else 21

        html = TEMPLATE.format(
            lang=s.get("lang", "en"),
            series=s["series"], brand=s["brand"], id=e["id"],
            prompt=s.get("prompt", s["series"]),
            title=e["title"], subtitle=e["subtitle"],
            tags=s.get("tags_line", s["brand"]),
            duration=s.get("duration", 18),
            acts_json=json.dumps(acts, ensure_ascii=False),
            phases_json=json.dumps(e.get("phases", ["", ""] * n), ensure_ascii=False),
            titles_json=json.dumps(e.get("titles", [e["title"]] * n), ensure_ascii=False),
            first_phase=(e.get("phases") or [""])[0],
            **ctx,
        )
        fn = out_dir / f"{s['series']}-{e['id']}-{s.get('suffix','916')}.html"
        fn.write_text(html, encoding="utf-8")

        spec = {
            "title": f"{s['brand']} — {e['title']}",
            "text": e["subtitle"],
            "duration": s.get("duration", 18),
            "fps": s.get("fps", 30),
            "width": s.get("width", 1080),
            "height": s.get("height", 1920),
            "scene_html": fn.name,
        }
        sp = SPECS / f"spec-{s['series']}-{e['id']}-{s.get('suffix','916')}.json"
        sp.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

        written.append({"episode": e["id"], "scene": str(fn), "spec": str(sp),
                        "sha256": hashlib.sha256(fn.read_bytes()).hexdigest()})
    return written


def selfcheck(scene: pathlib.Path) -> dict:
    """The four defects that have cost renders — asserted, not remembered."""
    h = scene.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', h)
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    refs = set(re.findall(r"getElementById\('([^']+)'\)", h))
    missing = sorted(refs - set(ids))
    canvas_tag = '<canvas id=' + '"c"'
    return {
        "duplicate_ids": dupes,
        "missing_targets": missing,
        "has_frame_hook": "window.__renderFrame" in h,
        "has_canvas": canvas_tag in h,
        "no_importmap": '<script type="importmap"' not in h,
        "no_module": 'type="module"' not in h,
        "has_wash": "createRadialGradient(W*0.5, H*0.46" in h,
        "ok": not dupes and not missing and "window.__renderFrame" in h
              and canvas_tag in h and '<script type="importmap"' not in h
              and 'type="module"' not in h
              and "createRadialGradient(W*0.5, H*0.46" in h,
    }


def register(s: dict, results: list[dict], do_probe: bool = True) -> dict:
    """Make the series findable with æQR.

    Each rendered episode becomes a registry entry: a stable id → a canonical
    route, with `verified` earned rather than assumed. An entry whose route does
    not answer is registered with verified:false and the reason recorded — the
    registry must not claim a resolution it did not observe.
    """
    import urllib.request
    reg_path = pathlib.Path(os.environ.get(
        "AEQR_REGISTRY", r"C:\æ\aeqr\registry\resources.json"))
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    lst = reg if isinstance(reg, list) else reg.get("resources")
    site = s.get("site", "https://myaelmendez.github.io")
    suffix = s.get("suffix", "916")

    added, updated, skipped = [], [], []
    for r in results:
        ep = r["episode"]
        rel = f"{s['series']}-{ep}-{suffix}.mp4"
        url = f"{site}/{rel}"
        rid = f"videos-{s['series']}-{ep}"

        verified, http, evidence = False, None, None
        if do_probe:
            try:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=20) as resp:
                    http = resp.status
                    verified = 200 <= resp.status < 300
            except urllib.error.HTTPError as e:
                http = e.code
            except Exception:
                http = 0
            if verified:
                evidence = {
                    "check": "http 200 on the canonical route",
                    "url": url,
                    "sha256": r.get("mp4_sha256") or "",
                    "at": time.strftime("%Y-%m-%d"),
                }
            else:
                evidence = {
                    "check": f"probe returned {http} — NOT verified",
                    "url": url,
                    "at": time.strftime("%Y-%m-%d"),
                }

        entry = {
            "id": rid, "name": rel, "path": rel, "category": "videos",
            "scope": "public", "route": url, "type": "video",
            "verified": verified, "evidence": evidence,
            # series metadata, so a finder can group without guessing
            "series": s["series"], "series_brand": s["brand"],
            "episode": ep, "episode_title": r.get("title", ""),
        }
        idx = next((i for i, x in enumerate(lst) if x.get("id") == rid), None)
        if idx is None:
            lst.append(entry); added.append(rid)
        elif lst[idx] != entry:
            lst[idx] = entry; updated.append(rid)
        else:
            skipped.append(rid)

    reg_path.write_text(json.dumps(lst if isinstance(reg, list) else reg,
                                   indent=2, ensure_ascii=False), encoding="utf-8")
    return {"added": added, "updated": updated, "unchanged": skipped,
            "total": len(lst), "registry": str(reg_path)}


def make_qr(s: dict, results: list[dict], out_dir: pathlib.Path | None = None) -> dict:
    """Emit a QR for the series — the scannable way to find all of it."""
    out_dir = out_dir or (AE / "github-pages" / "series")
    out_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(AE / "aeqr"))
    from ae import supervision as sup

    episodes = [{"episode": r["episode"], "url":
                 f"{s.get('site','https://myaelmendez.github.io')}/"
                 f"{s['series']}-{r['episode']}-{s.get('suffix','916')}.mp4",
                 "sha256": r.get("mp4_sha256", "")} for r in results]

    index = {
        "series": s["series"], "brand": s["brand"],
        "handle": s.get("handle", ""),
        "episodes": episodes,
        "count": len(episodes),
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    idx_path = out_dir / f"{s['series']}-index.json"
    idx_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    # the envelope carries the series index route — a scannable address, not a grant
    from ae import envelope as env_mod
    index_url = (f"{s.get('site','https://myaelmendez.github.io')}"
                 f"/series/{s['series']}-index.json")
    env = env_mod.encode("route", {"series": s["series"],
                                   "index": index_url,
                                   "count": len(episodes)})
    # cv2.imread cannot read a non-ASCII path on Windows (C:\æ\... returns None),
    # so produce at an ASCII staging path and then move the verified PNG.
    import tempfile
    import shutil
    stage = pathlib.Path(tempfile.gettempdir()) / f"ae-{s['series']}-qr.png"
    final = out_dir / f"{s['series']}-qr.png"
    receipt = sup.produce("route",
                          {"series": s["series"],
                           "index": index_url,
                           "count": len(episodes)},
                          out_path=stage)
    shutil.copy2(stage, final)
    return {"index": str(idx_path), "qr": str(final),
            "qr_passed": getattr(receipt, "passed", None),
            "envelope": env}


def main(argv):
    ap = argparse.ArgumentParser(description="a series is a spec, not a scene")
    sub = ap.add_subparsers(dest="cmd")
    for c in ("check", "emit", "render", "script", "register"):
        p = sub.add_parser(c)
        p.add_argument("series")
    rp = sub.add_parser("qr")
    rp.add_argument("series")
    a = ap.parse_args(argv[1:])

    if not a.cmd:
        ap.print_help(); return 1
    path = pathlib.Path(a.series)
    if not path.exists():
        print(f"  no such series: {path}"); return 1
    s = load(path)

    errs = validate(s)
    if errs:
        print("  INVALID:")
        for e in errs: print(f"    {e}")
        return 1
    print(f"  series  : {s['series']}  ({s['brand']})")
    print(f"  episodes: {len(s['episodes'])}")
    print(f"  frame   : {s.get('width',1080)}x{s.get('height',1920)} · "
          f"{s.get('duration',18)}s @ {s.get('fps',30)}fps")

    if a.cmd == "check":
        for e in s["episodes"]:
            kinds = [x["kind"] for x in e["acts"]]
            print(f"    {e['id']:18s} {len(e['acts'])} acts  {kinds}")
        print("  ✓ valid")
        return 0

    written = emit(s)
    print(f"\n  emitted {len(written)} scene(s):")
    allok = True
    for w in written:
        chk = selfcheck(pathlib.Path(w["scene"]))
        allok = allok and chk["ok"]
        print(f"    {'PASS' if chk['ok'] else 'FAIL'}  {pathlib.Path(w['scene']).name}")
        if not chk["ok"]:
            print(f"          {chk}")
    if not allok:
        print("\n  self-check FAILED — not rendering")
        return 1
    print("  ✓ all scenes pass the engine's self-check")

    if a.cmd == "render":
        print("\n  rendering (run this as a background job — one render "
              "outlasts a foreground timeout)")
        for w in written:
            ep = w["episode"]
            out = OUT / f"{s['series']}-{ep}-{s.get('suffix','916')}.mp4"
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists(): out.unlink()
            cmd = ["cmd", "/c",
                   r"cd /d C:\æ\store\mp4-factory-app && node vidaeo-producer.js "
                   + w["spec"] + " " + str(out)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if not out.exists():
                print(f"    FAIL {ep}: producer produced nothing")
                print("    " + (r.stdout or "")[-300:])
                continue
            v = subprocess.run([GPU, str(AE/"vidæo"/"vidæo.py"), "verify", str(out)],
                               capture_output=True, text=True, timeout=400)
            line = [l for l in (v.stdout or "").split("\n") if "PASS" in l or "FAIL" in l]
            print(f"    {ep}: {line[0].strip() if line else 'gate output unreadable'}")

    if a.cmd == "script":
        print("\n  == script pipeline ==")
        for w in written:
            ep = w["episode"]
            scene_path = pathlib.Path(w["scene"])
            out = OUT / f"{s['series']}-{ep}-{s.get('suffix','916')}.mp4"
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists(): out.unlink()

            print(f"\n  [emit]")
            print(f"    scene   {scene_path}")
            print(f"    sha256  {w['sha256']}")

            print(f"  [render]")
            cmd = ["cmd", "/c",
                   r"cd /d C:\æ\store\mp4-factory-app && node vidaeo-producer.js "
                   + w["spec"] + " " + str(out)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if not out.exists():
                print(f"    result  FAIL — producer produced nothing")
                print("    " + (r.stdout or "")[-300:])
                continue
            print(f"    result  OK — {out.stat().st_size} bytes")

            print(f"  [gate]")
            v = subprocess.run([GPU, str(AE/"vidæo"/"vidæo.py"), "verify", str(out)],
                               capture_output=True, text=True, timeout=400)
            line = [l for l in (v.stdout or "").split("\n") if "PASS" in l or "FAIL" in l]
            gate_result = line[0].strip() if line else "gate output unreadable"
            print(f"    result  {gate_result}")

            mp4_sha = hashlib.sha256(out.read_bytes()).hexdigest()
            print(f"  [sha256] {mp4_sha}")
        print("\n  == end script ==")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
