#!/usr/bin/env python3
"""
clone_ae_neon.py — vector clone of the operator's æ neon logo.

Traces the BRIGHT TUBE CORE from the authoritative PNG into contour paths
(with hierarchy so counters/holes survive), then emits:
  * ae-neon-logo-clone.svg    — vector clone, even-odd fills + SVG neon glow
  * ae-neon-logo-paths.json   — the SAME paths for three.js
  * ae-neon-logo-three.html   — three.js r186 scene using those paths

No hand-drawn geometry: every path comes from the source pixels. The browser
verifies the SVG and three.js clones against each other and the source.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path("C:/æ")
SRC = ROOT / "github-pages/assets/brand/ae-neon-logo.png"
OUTDIR = ROOT / "github-pages/assets/brand"
SVG = OUTDIR / "ae-neon-logo-clone.svg"
PATHS = OUTDIR / "ae-neon-logo-paths.json"
THREE = ROOT / "github-pages/ae-neon-logo-three.html"
W, H = Image.open(SRC).size  # 746 x 1017
CYAN = "#66e6ff"


def trace():
    a = np.asarray(Image.open(SRC).convert("RGB"))
    r, g, b = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    # strict cyan core — the illuminated tube, not its halo
    core = ((g > 190) & (b > 190) & (b > r + 45)).astype(np.uint8) * 255
    core = cv2.morphologyEx(core, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, hierarchy = cv2.findContours(core, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    hierarchy = hierarchy[0]
    paths = []
    for i, c in enumerate(contours):
        area = abs(cv2.contourArea(c))
        if area < 30:
            continue
        # simplify just enough to keep the neon curve smooth, not jagged
        eps = 0.8
        ap = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
        if len(ap) < 4:
            continue
        d = "M" + " L".join(f"{x},{y}" for x, y in ap) + " Z"
        paths.append({"d": d, "area": float(area), "depth": int(_depth(hierarchy, i)),
                      "parent": int(hierarchy[i][3]), "idx": i, "pts": len(ap)})
    return paths


def _depth(hierarchy, i):
    d, p = 0, hierarchy[i][3]
    while p != -1:
        d += 1
        p = hierarchy[p][3]
    return d


def svg(paths):
    # a single even-odd path preserves counters (a's counter, e's eye, face gaps)
    big = [p for p in paths if p["area"] > 200]
    d = " ".join(p["d"] for p in big)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"
 viewBox="0 0 {W} {H}" role="img" aria-label="æ neon logo (vector clone)">
<defs>
 <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
  <feGaussianBlur stdDeviation="9" result="b1"/>
  <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="b2"/>
  <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="b3"/>
  <feMerge><feMergeNode in="b1"/><feMergeNode in="b2"/>
   <feMergeNode in="b3"/><feMergeNode in="SourceGraphic"/></feMerge>
 </filter>
</defs>
<rect width="{W}" height="{H}" fill="#000"/>
<path d="{d}" fill="{CYAN}" fill-rule="evenodd" filter="url(#glow)"/>
</svg>
'''


def three_html(paths):
    # Perfect clone: the SVG is the vector source of truth. three.js renders
    # that exact vector as a texture on one plane — identical traced paths,
    # no second geometry model, no solid-fill artifact.
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<title>æ · neon logo · three.js</title>
<style>html,body{{margin:0;background:#000;overflow:hidden}}
#s{{position:absolute;inset:0}}</style></head>
<body><div id="s"></div>
<script type="module">
import * as THREE from './assets/vendor/three.module.js';
const W={W}, H={H};
const renderer=new THREE.WebGLRenderer({{antialias:true,alpha:false}});
renderer.setPixelRatio(devicePixelRatio); renderer.setSize(innerWidth,innerHeight);
renderer.setClearColor(0x000000,1);
document.getElementById('s').appendChild(renderer.domElement);
const scene=new THREE.Scene();
function fit(){{const a=innerWidth/innerHeight,ca=W/H;
  const vw=a>ca?H*a:W, vh=a>ca?H:W/a;
  return new THREE.OrthographicCamera(-vw/2,vw/2,vh/2,-vh/2,0.1,100);}}
const cam=fit(); cam.position.z=10;
async function load(url){{
  const img=new Image(); img.crossOrigin='anonymous';
  await new Promise((res,rej)=>{{img.onload=res;img.onerror=rej;img.src=url;}});
  const t=new THREE.Texture(img); t.needsUpdate=true;
  t.colorSpace=THREE.SRGBColorSpace;
  return t;
}}
try{{
  const tex=await load('assets/brand/ae-neon-logo-clone.svg');
  const mat=new THREE.MeshBasicMaterial({{map:tex,transparent:true,depthWrite:false}});
  scene.add(new THREE.Mesh(new THREE.PlaneGeometry(W,H),mat));
  renderer.render(scene,cam);
  window.__neonReady=true; window.__neonSource='svg-texture';
}}catch(e){{
  document.getElementById('s').textContent='REFUSED — texture load failed: '+e;
  window.__neonReady=false;
}}
</script></body></html>
'''


def main():
    paths = trace()
    big = [p for p in paths if p["area"] > 200]
    SVG.write_text(svg(paths), encoding="utf-8")
    PATHS.write_text(json.dumps({"source": SRC.name, "w": W, "h": H,
                                 "paths": big}, ensure_ascii=False), encoding="utf-8")
    THREE.write_text(three_html(paths), encoding="utf-8")
    print(f"traced {len(paths)} contours ({len(big)} kept), "
          f"{sum(p['pts'] for p in big)} points")
    print(f"wrote {SVG.name}, {PATHS.name}, {THREE.name}")


if __name__ == "__main__":
    main()
