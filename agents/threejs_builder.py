#!/usr/bin/env python3
"""
threejs_builder.py — the same series spec, rendered by Three.js/WebGL.

THREE RENDER PATHS, ONE CONTENT CONTRACT
----------------------------------------
The series JSON is data. The render path is a choice:

    series.json  →  canvas  (HTML + Canvas 2D + CDP + NVENC)
               →  manim   (Python + Manim CE + ffmpeg)
               →  threejs (Three.js/WebGL + render.mjs + NVENC)

This builder emits a Three.js scene with the SAME act kinds (intro, list,
blocks, outro, timeline, compare) — translated to 3D objects, animations,
and camera movements. The scene exposes window.__renderFrame(i, total) so
render.mjs can drive it deterministically.

COMMANDS
    python threejs_builder.py emit   <series.json>   # write scene .html + render spec
    python threejs_builder.py check  <series.json>   # validate + report
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

AE = pathlib.Path(os.environ.get("AE_ROOT", r"C:\æ"))
SCENES = AE / "site" / "aipodcast_me"
SPECS = AE / "studio" / "specs"

HEADER = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={w},height={h}">
<title>{brand} — {title}</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@4000;700&family=Orbitron:wght@700;900&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;background:#050505;font-family:'JetBrains Mono',monospace}}
canvas{{position:fixed;top:0;left:0;width:{w}px;height:{h}px;display:block;z-index:1}}
</style>
</head>
<body>
<canvas id="c"></canvas>
<script type="module">
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.167.0/build/three.module.js';

const W = {w}, H = {h}, DURATION = {duration};
const cv = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({{ canvas: cv, antialias: true }});
renderer.setSize(W, H);
renderer.setPixelRatio(1);

const scene = new THREE.Scene();
scene.background = new THREE.Color('#050505');
scene.fog = new THREE.FogExp2('#050505', 0.02);

const camera = new THREE.PerspectiveCamera(60, W/H, 0.1, 1000);
camera.position.set(0, 0, 18);

const GOLD = 0xD4AF37, GOLDHI = 0xFFD700, CYAN = 0x00EAFF, NEON = 0x00FF9D, TXT = 0xF2EFE6;

// warm wash — a large gradient plane behind everything
const washGeo = new THREE.PlaneGeometry(W*2, H*2);
const washMat = new THREE.MeshBasicMaterial({{
  color: 0x050505, transparent: true, opacity: 0.96,
  side: THREE.DoubleSide
}});
const wash = new THREE.Mesh(washGeo, washMat);
wash.position.z = -20;
scene.add(wash);

// radial glow
const glowGeo = new THREE.CircleGeometry(8, 32);
const glowMat = new THREE.MeshBasicMaterial({{
  color: GOLD, transparent: true, opacity: 0.08, side: THREE.DoubleSide
}});
const glow = new THREE.Mesh(glowGeo, glowMat);
glow.position.z = -15;
scene.add(glow);

// particle field
const pGeo = new THREE.BufferGeometry();
const pCount = 800;
const pPos = new Float32Array(pCount * 3);
const pCol = new Float32Array(pCount * 3);
for (let i = 0; i < pCount; i++) {{
  pPos[i*3]   = (Math.random()-0.5) * W * 1.5;
  pPos[i*3+1] = (Math.random()-0.5) * H * 1.5;
  pPos[i*3+2] = -5 + Math.random() * 20;
  const c = Math.random() < 0.25 ? GOLDHI : (Math.random() < 0.5 ? GOLD : CYAN);
  pCol[i*3]   = ((c >> 16) & 255) / 255;
  pCol[i*3+1] = ((c >> 8) & 255) / 255;
  pCol[i*3+2] = (c & 255) / 255;
}}
pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
pGeo.setAttribute('color', new THREE.BufferAttribute(pCol, 3));
const pMat = new THREE.PointsMaterial({{ size: 0.05, vertexColors: true, transparent: true, opacity: 0.7 }});
const particles = new THREE.Points(pGeo, pMat);
scene.add(particles);

// text sprites — canvas-based texture
function makeTextSprite(text, color, size=48) {{
  const c = document.createElement('canvas');
  c.width = 1024; c.height = 256;
  const g = c.getContext('2d');
  g.clearRect(0, 0, 1024, 256);
  g.font = `900 ${{size}}px "Orbitron", sans-serif`;
  g.fillStyle = color;
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.fillText(text, 512, 128);
  const tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({{ map: tex, transparent: true, depthWrite: false }});
  const sp = new THREE.Sprite(mat);
  sp.scale.set(8, 2, 1);
  return sp;
}}

function makeTextSpriteSmall(text, color, size=28) {{
  const c = document.createElement('canvas');
  c.width = 1024; c.height = 128;
  const g = c.getContext('2d');
  g.clearRect(0, 0, 1024, 128);
  g.font = `400 ${{size}}px "JetBrains Mono", monospace`;
  g.fillStyle = color;
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.fillText(text, 512, 64);
  const tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({{ map: tex, transparent: true, depthWrite: false }});
  const sp = new THREE.Sprite(mat);
  sp.scale.set(10, 1.25, 1);
  return sp;
}}

'''

ACT_INTRO = '''
// ACT {i}: intro
(() => {{
  const sp = makeTextSprite({big!r}, '#FFD700', 72);
  sp.position.set(0, 2, 0);
  sp.material.opacity = 0;
  scene.add(sp);
  const subs = [];
  {lines_setup}
  window.__acts[window.__actCount++] = {{ obj: sp, subs: subs, kind: 'intro' }};
}})();
'''

ACT_LIST = '''
// ACT {i}: list
(() => {{
  const group = new THREE.Group();
  group.position.set(0, 0, 0);
  const rows = [];
  {rows_setup}
  scene.add(group);
  window.__acts[window.__actCount++] = {{ obj: group, rows: rows, kind: 'list' }};
}})();
'''

ACT_BLOCKS = '''
// ACT {i}: blocks
(() => {{
  const group = new THREE.Group();
  const cards = [];
  {cards_setup}
  scene.add(group);
  window.__acts[window.__actCount++] = {{ obj: group, cards: cards, kind: 'blocks' }};
}})();
'''

ACT_OUTRO = '''
// ACT {i}: outro
(() => {{
  const group = new THREE.Group();
  const lines = [];
  {lines_setup}
  scene.add(group);
  window.__acts[window.__actCount++] = {{ obj: group, lines: lines, kind: 'outro' }};
}})();
'''

ACT_TIMELINE = '''
// ACT {i}: timeline
(() => {{
  const group = new THREE.Group();
  const events = [];
  {events_setup}
  scene.add(group);
  window.__acts[window.__actCount++] = {{ obj: group, events: events, kind: 'timeline' }};
}})();
'''

ACT_COMPARE = '''
// ACT {i}: compare
(() => {{
  const group = new THREE.Group();
  const panels = [];
  {panels_setup}
  scene.add(group);
  window.__acts[window.__actCount++] = {{ obj: group, panels: panels, kind: 'compare' }};
}})();
'''

FOOTER = '''
// ── deterministic render hook ──
window.__actCount = 0;
window.__acts = [];

function ease(t){{ return t < 0.5 ? 2*t*t : 1 - Math.pow(-2*t+2, 2)/2; }}
function seg(t, a, b){{ return Math.max(0, Math.min(1, (t-a)/(b-a))); }}

window.__renderFrame = function(i, total) {{
  const n = Math.max(1, total - 1);
  const t = (i / n) * DURATION;
  const actN = window.__acts.length;
  const span = DURATION / Math.max(1, actN);
  const idx = Math.min(actN - 1, Math.floor(t / span));
  const local = (t - idx*span) / span;
  const fade = ease(seg(local, 0, 0.12)) * (1 - ease(seg(local, 0.88, 1)));
  for (let k = 0; k < window.__acts.length; k++) {{
    const a = window.__acts[k];
    const on = k === idx ? fade : 0;
    if (a.kind === 'intro') {{
      a.obj.material.opacity = on;
      a.obj.position.y = 2 + (1-on)*0.5;
      a.subs.forEach((s, j) => {{
        s.material.opacity = on * ease(seg(local, 0.2+j*0.18, 0.5+j*0.18));
      }});
    }} else if (a.kind === 'list') {{
      a.rows.forEach((r, j) => {{
        const rp = on * ease(seg(local, 0.1+j*0.12, 0.4+j*0.12));
        r.key.material.opacity = rp;
        r.val.material.opacity = rp;
        r.key.position.y = r.y + (1-rp)*0.3;
        r.val.position.y = r.y + (1-rp)*0.3;
      }});
      if (a.foot) a.foot.material.opacity = on * ease(seg(local, 0.8, 0.95));
    }} else if (a.kind === 'blocks') {{
      a.cards.forEach((c, j) => {{
        const cp = on * ease(seg(local, 0.15+j*0.18, 0.45+j*0.18));
        c.box.material.opacity = cp;
        c.box.scale.setScalar(0.6 + 0.4*cp);
        c.title.material.opacity = cp;
        if (c.sub) c.sub.material.opacity = cp;
      }});
      if (a.closer) a.closer.material.opacity = on * ease(seg(local, 0.85, 1));
    }} else if (a.kind === 'outro') {{
      a.lines.forEach((l, j) => {{
        l.material.opacity = on * ease(seg(local, 0.15+j*0.2, 0.5+j*0.2));
      }});
    }} else if (a.kind === 'timeline') {{
      a.events.forEach((e, j) => {{
        const ep = on * ease(seg(local, 0.15+j*0.15, 0.5+j*0.15));
        e.dot.material.opacity = ep;
        e.key.material.opacity = ep;
        e.label.material.opacity = ep;
      }});
      if (a.closer) a.closer.material.opacity = on * ease(seg(local, 0.85, 1));
    }} else if (a.kind === 'compare') {{
      a.panels.forEach((p, j) => {{
        const pp = on * ease(seg(local, 0.2+j*0.3, 0.5+j*0.3));
        p.box.material.opacity = pp;
        p.box.scale.setScalar(0.6 + 0.4*pp);
        p.title.material.opacity = pp;
        if (p.sub) p.sub.material.opacity = pp;
      }});
      if (a.closer) a.closer.material.opacity = on * ease(seg(local, 0.85, 1));
    }}
  }}
  particles.rotation.z = t * 0.01;
  glow.material.opacity = 0.06 + 0.03*Math.sin(t*1.5);
  camera.position.x = Math.sin(t*0.2) * 1.2;
  camera.position.y = Math.cos(t*0.15) * 0.8;
  camera.lookAt(0, 0, 0);
  renderer.render(scene, camera);
  return true;
}};

// boot
window.__renderFrame(0, 1);
</script>
</body>
</html>
'''

ACT_TEMPLATES = {
    "intro": ACT_INTRO,
    "list": ACT_LIST,
    "blocks": ACT_BLOCKS,
    "outro": ACT_OUTRO,
    "timeline": ACT_TIMELINE,
    "compare": ACT_COMPARE,
}


def emit(s: dict, out_dir: pathlib.Path | None = None) -> list[dict]:
    out_dir = out_dir or SCENES
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for e in s["episodes"]:
        acts = e["acts"]
        act_codes = []
        for i, a in enumerate(acts):
            kind = a["kind"]
            if kind not in ACT_TEMPLATES:
                continue
            tpl = ACT_TEMPLATES[kind]
            big = a.get("big", "")
            lines = a.get("lines", [])
            items = a.get("items", [])
            lines_setup = ""
            for j, ln in enumerate(lines):
                color = ln[1] if len(ln) > 1 else "TXT"
                lines_setup += f"  const sub{j} = makeTextSpriteSmall({ln[0]!r}, #{color});\n"
                lines_setup += f"  sub{j}.position.set(0, {2 - 1.2*(j+1)}, 0);\n"
                lines_setup += f"  scene.add(sub{j});\n"
                lines_setup += f"  subs.push(sub{j});\n"
            rows_setup = ""
            for j, (k, label) in enumerate(items):
                rows_setup += f"  const k{j} = makeTextSpriteSmall({k!r}, '#D4AF37', 32);\n"
                rows_setup += f"  k{j}.position.set(-5.2, {1.6 - j*0.62}, 0);\n"
                rows_setup += f"  scene.add(k{j});\n"
                rows_setup += f"  const v{j} = makeTextSpriteSmall({label!r}, '#F2EFE6', 28);\n"
                rows_setup += f"  v{j}.position.set(-2.0, {1.6 - j*0.62}, 0);\n"
                rows_setup += f"  scene.add(v{j});\n"
                rows_setup += f"  rows.push({{ key: k{j}, val: v{j}, y: {1.6 - j*0.62} }});\n"
            cards_setup = ""
            for j, it in enumerate(items):
                color = "#FFD700" if j == 0 else ("#00EAFF" if j == 1 else "#00FF9D")
                cards_setup += f"  const box{j} = new THREE.Mesh(\n"
                cards_setup += f"    new THREE.BoxGeometry(3.5, 1.4, 0.1),\n"
                cards_setup += f"    new THREE.MeshBasicMaterial({{ color: {color}, transparent: true, opacity: 0 }})\n"
                cards_setup += f"  );\n"
                cards_setup += f"  box{j}.position.set({-3.2 + j*6.4}, 0, 0);\n"
                cards_setup += f"  scene.add(box{j});\n"
                cards_setup += f"  const t{j} = makeTextSprite({it[0]!r}, '{color}', 34);\n"
                cards_setup += f"  t{j}.position.set({-3.2 + j*6.4}, 0.3, 0.1);\n"
                cards_setup += f"  scene.add(t{j});\n"
                if len(it) > 1:
                    cards_setup += f"  const s{j} = makeTextSpriteSmall({it[1]!r}, '#00EAFF', 22);\n"
                    cards_setup += f"  s{j}.position.set({-3.2 + j*6.4}, -0.4, 0.1);\n"
                    cards_setup += f"  scene.add(s{j});\n"
                cards_setup += f"  cards.push({{ box: box{j}, title: t{j}{', sub: s' + str(j) if len(it) > 1 else ''} }});\n"
            events_setup = ""
            for j, it in enumerate(items):
                x = -5.5 + j * (11.0 / max(1, len(items) - 1))
                events_setup += f"  const dot{j} = new THREE.Mesh(\n"
                events_setup += f"    new THREE.SphereGeometry(0.09, 16, 16),\n"
                events_setup += f"    new THREE.MeshBasicMaterial({{ color: 0xFFD700, transparent: true, opacity: 0 }})\n"
                events_setup += f"  );\n"
                events_setup += f"  dot{j}.position.set({x}, 0, 0);\n"
                events_setup += f"  scene.add(dot{j});\n"
                events_setup += f"  const k{j} = makeTextSpriteSmall({it[0]!r}, '#D4AF37', 32);\n"
                events_setup += f"  k{j}.position.set({x}, 0.5, 0);\n"
                events_setup += f"  scene.add(k{j});\n"
                events_setup += f"  const l{j} = makeTextSpriteSmall({it[1]!r}, '#F2EFE6', 26);\n"
                events_setup += f"  l{j}.position.set({x}, -0.5, 0);\n"
                events_setup += f"  scene.add(l{j});\n"
                events_setup += f"  events.push({{ dot: dot{j}, key: k{j}, label: l{j} }});\n"
            panels_setup = ""
            for j, it in enumerate(items):
                if j >= 2:
                    break
                color = "#FFD700" if j == 0 else "#00FF9D"
                panels_setup += f"  const pbox{j} = new THREE.Mesh(\n"
                panels_setup += f"    new THREE.BoxGeometry(4.5, 4.2, 0.1),\n"
                panels_setup += f"    new THREE.MeshBasicMaterial({{ color: {color}, transparent: true, opacity: 0 }})\n"
                panels_setup += f"  );\n"
                panels_setup += f"  pbox{j}.position.set({-3.4 + j*6.8}, 0, 0);\n"
                panels_setup += f"  scene.add(pbox{j});\n"
                panels_setup += f"  const pt{j} = makeTextSprite({it[0]!r}, '{color}', 32);\n"
                panels_setup += f"  pt{j}.position.set({-3.4 + j*6.8}, 0.8, 0.1);\n"
                panels_setup += f"  scene.add(pt{j});\n"
                if len(it) > 1:
                    panels_setup += f"  const ps{j} = makeTextSpriteSmall({it[1]!r}, '#00EAFF', 20);\n"
                    panels_setup += f"  ps{j}.position.set({-3.4 + j*6.8}, 0.3, 0.1);\n"
                panels_setup += f"  panels.push({{ box: pbox{j}, title: pt{j}{', sub: ps' + str(j) if len(it) > 1 else ''} }});\n"
            setup = ""
            if kind == "intro":
                setup = lines_setup
            elif kind == "list":
                setup = rows_setup
            elif kind == "blocks":
                setup = cards_setup
            elif kind == "outro":
                setup = lines_setup
            elif kind == "timeline":
                setup = events_setup
            elif kind == "compare":
                setup = panels_setup
            code = tpl.replace("{i}", str(i)).replace("{kind}", kind)
            code = code.replace("{big!r}", repr(big))
            code = code.replace("{lines_setup}", setup)
            code = code.replace("{rows_setup}", setup)
            code = code.replace("{cards_setup}", setup)
            code = code.replace("{events_setup}", setup)
            code = code.replace("{panels_setup}", setup)
            act_codes.append(code)
        html = HEADER.format(
            brand=s["brand"], title=e["title"],
            w=s.get("width", 1920), h=s.get("height", 1080),
            duration=s.get("duration", 18),
        ) + "\n".join(act_codes) + FOOTER
        fn = out_dir / f"{s['series']}-{e['id']}-{s.get('suffix','916')}-threejs.html"
        fn.write_text(html, encoding="utf-8")
        spec = {
            "title": f"{s['brand']} — {e['title']}",
            "text": e["subtitle"],
            "duration": s.get("duration", 18),
            "fps": s.get("fps", 30),
            "width": s.get("width", 1920),
            "height": s.get("height", 1080),
            "scene_html": fn.name,
            "render_path": "threejs",
        }
        sp = SPECS / f"spec-{s['series']}-{e['id']}-{s.get('suffix','916')}-threejs.json"
        sp.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append({"episode": e["id"], "scene": str(fn), "spec": str(sp)})
    return written


def main(argv):
    ap = argparse.ArgumentParser(description="the same spec, rendered by Three.js")
    sub = ap.add_subparsers(dest="cmd")
    for c in ("check", "emit"):
        p = sub.add_parser(c)
        p.add_argument("series")
    a = ap.parse_args(argv[1:])

    path = pathlib.Path(a.series)
    if not path.exists():
        print(f"  no such series: {path}"); return 1
    s = json.loads(path.read_text(encoding="utf-8"))

    if a.cmd == "check":
        for e in s["episodes"]:
            kinds = [x["kind"] for x in e["acts"]]
            print(f"    {e['id']:18s} {len(e['acts'])} acts  {kinds}")
        print("  ✓ valid")
        return 0

    written = emit(s)
    print(f"\n  emitted {len(written)} Three.js scene(s):")
    for w in written:
        print(f"    {pathlib.Path(w['scene']).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
