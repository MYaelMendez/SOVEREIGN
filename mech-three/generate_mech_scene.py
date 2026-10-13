#!/usr/bin/env python3
"""mech-three — Generate three.js canvas scenes from Mech state-machine specs.

The bridge between Mech grammar (mech-lang.org) and the three.js render
pipeline. A Mech spec declares the reactive dataflow; this generator emits
a classical canvas scene with:
  - <canvas id="c"> (canvas mode, NOT module/importmap)
  - window.__renderFrame(i, total) hook (deterministic, frame-paced)
  - drawScene(time) animation loop (reactive dataflow)
  - Three.js via classic <script> tags (NOT module/importmap)

The spec says WHAT the dataflow is; the generated scene says HOW to draw it.
"""

import json, hashlib, re
from pathlib import Path
from dataclasses import dataclass

# ── Mech spec model ────────────────────────────────────────────────
ARROW = "\u2192"
PRODUCES = "\u21d2"
BRANCH = "\u251c"
TERM = "\u2514"
ASSIGN = ":="

_STAGE = re.compile(r":([A-Z][A-Za-z0-9_]*)")

@dataclass
class MechSpec:
    name: str
    stages: list
    edges: list
    terminals: list
    refusals: list
    raw: str
    sha256: str

# ── Colors ─────────────────────────────────────────────────────────
GOLD = "#D4AF37"
VOID = "#050505"
CYAN = "#00FFFF"
GREEN = "#00FF00"
PURPLE = "#FF00FF"
WHITE = "#FFFFFF"

def colors_for_stages(stages):
    palette = [GOLD, CYAN, GREEN, PURPLE, WHITE]
    return [palette[i % len(palette)] for i in range(len(stages))]

def generate_scene_code(spec, colors):
    """Generate three.js canvas scene JS code as a plain string."""
    stages = spec.stages
    edges = spec.edges
    out = []
    L = out.append
    L('const { WebGLRenderer, Scene, PerspectiveCamera, Color, Vector3, BufferGeometry, Float32BufferAttribute, Points, PointsMaterial } = window THREE = window THREE || {};')
    L('const renderer = new WebGLRenderer({ antialias: true });')
    L('renderer.setSize(window.innerWidth, window.innerHeight);')
    L('renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));')
    L('renderer.setClearColor(new THREE.Color({ r:0, g:0, b:0 }));')
    L('renderer.shadowMap.enabled = true;')
    L('renderer.shadowMap.type = THREE.PCFSoftShadowMap;')
    L('document.body.prepend(renderer.domElement);')
    L('')
    L('const scene = new THREE.Scene();')
    L('const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);')
    L('camera.position.set(0, 0, 180);')
    L('')
    L('const nodeColors = {')
    for stage, color in zip(stages, colors):
        L(f"  '{stage}': '{color}',")
    L('};')
    L('')
    L('const nodes = {};')
    for stage in stages:
        L(f'const {stage}Mesh = new THREE.Mesh(')
        L(f"  new THREE.SphereGeometry(8, 32, 32),")
        L(f"  new THREE.MeshStandardMaterial({{ color: new THREE.Color(nodeColors['{stage}']), emissive: new THREE.Color(nodeColors['{stage}']), emissiveIntensity: 0.6, roughness: 0.3, metalness: 0.7 }});")
        L(f'scene.add({stage}Mesh);')
        L(f'nodes["{stage}"] = {stage}Mesh;')
    L('')
    L('const lineMat = new THREE.LineBasicMaterial({ color: 0x808080, transparent: true, opacity: 0.25 });')
    L('const lines = [];')
    for a, b in edges:
        L(f'lines.push(new THREE.LineSegments(')
        L('  new THREE.BufferGeometry().setFromPoints([')
        L('    new THREE.Vector3(0, 0, 0),')
        L('    new THREE.Vector3(0, 0, 120)')
        L('  ]), lineMat);')
    L('')
    L('const particleCount = 300;')
    L('const positions = new Float32Array(particleCount * 3);')
    L('for (let i = 0; i < particleCount; i++) {')
    L('  positions[i*3] = (Math.random() - 0.5) * 360;')
    L('  positions[i*3+1] = (Math.random() - 0.5) * 360;')
    L('  positions[i*3+2] = Math.random() * 170 + 10;')
    L('}')
    L('const particleGeo = new THREE.BufferGeometry();')
    L("particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));")
    L("const particleMat = new THREE.PointsMaterial({ color: 0xD4AF37, size: 0.5, transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending });")
    L("const particles = new THREE.Points(particleGeo, particleMat);")
    L('')
    L('const amb = new THREE.AmbientLight({ color: new THREE.Color(0xD4AF37), intensity: 0.2 });')
    L('scene.add(amb);')
    L('const dir = new THREE.DirectionalLight({ color: new THREE.Color(0xD4AF37), intensity: 0.6, position: new THREE.Vector3(50, 80, 60) });')
    L('dir.castShadow = true;')
    L('scene.add(dir);')
    L('const key = new THREE.DirectionalLight({ color: new THREE.Color(0x00FF00), intensity: 0.3, position: new THREE.Vector3(-40, 20, -30) });')
    L('scene.add(key);')
    L('const fill = new THREE.DirectionalLight({ color: new THREE.Color(0x00FFFF), intensity: 0.25, position: new THREE.Vector3(30, -20, 40) });')
    L('scene.add(fill);')
    L('')
    L('const gridHelper = new THREE.GridHelper(280, 30, 0xD4AF37, 0x00FFFF);')
    L('scene.add(gridHelper);')
    L('')
    L('// ── Render loop ──')
    L('let frame = 0;')
    L('window.__renderFrame = function(i, total) {')
    L('  frame = i;')
    L('  const time = i / (total - 1) * 6; // 6 second cycle')
    L('  // Reactive dataflow: node positions follow Mech signals')
    L('  for (const stage of Object.keys(nodes)) {')
    L(f"    const mesh = nodes[stage];")
    L('    mesh.rotation.x += 0.01;')
    L(f"    mesh.position.y = 15 + 12 * Math.sin(time * 0.8 + {stages.index(stage)*1.2});")
    L(f"    mesh.material.color.setHex({colors[stages.index(stage)].replace('#','0x')});")
    L(f"    mesh.material.emissive.setHex({colors[stages.index(stage)].replace('#','0x')});")
    L('  }')
    L('')
    L('  renderer.setClearColor(new THREE.Color(0x050505));')
    L('  renderer.render(scene, camera);')
    L('}')
    L('')
    L('window.addEventListener("resize", () => {')
    L('  camera.aspect = window.innerWidth / window.innerHeight;')
    L('  camera.updateProjectionMatrix();')
    L('  renderer.setSize(window.innerWidth, window.innerHeight);')
    L('})')
    return "\n".join(out)

def generate_mech_three_js(spec: MechSpec) -> str:
    """Generate the full HTML scene from a Mech spec."""
    stages = spec.stages
    edges = spec.edges
    colors = colors_for_stages(stages)

    dag_lines = [f'<div class="dag-line"><span class="dag-node">{a}</span> <span class="dag-edge">\u2192</span> <span class="dag-node">{b}</span></div>' for a, b in edges]
    scene_code = generate_scene_code(spec, colors)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>æ:// mech {spec.name} — reactive dataflow</title>
<style>
  :root {{
    --mech-gold: {GOLD};
    --mech-voa: {VOID};
    --mech-cyan: {CYAN};
    --mech-green: {GREEN};
    --mech-purple: {PURPLE};
    --mech-white: {WHITE};
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {VOID};
    overflow: hidden;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    color: {GOLD};
    cursor: crosshair;
  }}
  #c {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; display: block; }}
  .ui {{ position: fixed; z-index: 100; pointer-events: none; }}
  .header {{
    position: absolute; top: 0; left: 0; right: 0; padding: 12px 20px;
    display: flex; justify-content: space-between; align-items: center;
    pointer-events: auto;
  }}
  .title {{
    font-family: 'Orbitron', sans-serif; font-weight: 700;
    font-size: clamp(14px, 2.5vw, 22px); letter-spacing: 2px;
    color: {GOLD}; text-shadow: 0 0 12px rgba(212,175,55,0.4);
  }}
  .tabs {{
    display: flex; gap: 6px;
  }}
  .tab {{
    padding: 4px 16px; border-radius: 6px; font-size: 11px;
    font-family: 'JetBrains Mono', monospace; color: {VOID};
    background: rgba(212,175,55,0.12); border: 1px solid rgba(212,175,55,0.3);
  }}
  .tab.active {{ background: {GOLD}; color: {VOID}; border-color: {GOLD}; }}
  .dag-panel {{
    position: absolute; top: 0; right: 0; bottom: 0; width: clamp(280px, 35vw, 400px);
    background: rgba(0,0,0,0.7); border: 1px solid rgba(212,175,55,0.3);
    padding: 16px; overflow-y: auto; font-size: clamp(10px, 1.8vw, 14px);
    line-height: 1.6; pointer-events: auto;
  }}
  .dag-panel h3 {{
    margin: 0 0 10px; font-family: 'Orbitron', sans-serif; font-size: clamp(14px,2vw,18px);
    color: {GOLD}; text-shadow: 0 0 8px rgba(212,175,55,0.3);
  }}
  .dag-line {{ color: {CYAN}; margin: 2px 0; }}
  .dag-node {{ color: {GOLD}; font-weight: bold; }}
  .dag-edge {{ color: {CYAN}; }}
  .stat-row {{ display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px dashed rgba(212,175,55,0.2); }}
  .stat-label {{ color: {VOID}; }}
  .stat-value {{ color: {GOLD}; font-family: 'JetBrains Mono', monospace; }}
  .footer {{
    position: absolute; bottom: 0; left: 0; right: 0; padding: 12px 20px;
    font-size: 11px; color: {VOID}; font-family: 'JetBrains Mono', monospace;
  }}
  .footer span {{ color: {GOLD}; }}
  .scanlines {{
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(212,175,55,0.02) 2px, rgba(212,175,55,0.02) 4px);
    pointer-events: none; z-index: 0;
  }}
</style>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
</head>
<body>
<div class="scanlines"></div>
<canvas id="c"></canvas>

<div class="ui header">
  <div class="title">&#128203; æ:// mech {spec.name} — reactive dataflow</div>
  <div class="tabs">
    <span class="tab active">mech</span>
    <span class="tab">three.js</span>
    <span class="tab">RTX 3050</span>
  </div>
</div>

<div class="dag-panel">
  <h3>&#128203; Reactive dataflow</h3>
  {chr(10).join(dag_lines)}
  <div class="stat-row"><span class="stat-label">states</span><span class="stat-value">{len(stages)}</span></div>
  <div class="stat-row"><span class="stat-label">transitions</span><span class="stat-value">{len(edges)}</span></div>
  <div class="stat-row"><span class="stat-label">sha256</span><span class="stat-value">{spec.sha256[:16]}</span></div>
</div>

<div class="ui footer">
  <span>&#128203; mech</span> &nbsp;&#128203; &nbsp;<a href="https://myaelmendez.github.io/mech-3d-webgl-engine.html">three.js</a> &nbsp;&#128203; &nbsp;RTX 3050 &nbsp;&#128203; &nbsp;<a href="https://myaelmendez.github.io/mech-3d-os.html">mech-3d-os</a>
</div>

<script>
{scene_code}
</script>
</body>
</html>
'''
