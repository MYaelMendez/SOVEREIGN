#!/usr/bin/env python3
"""
Render fleet-waves-development.mp4 — the story of æ:// fleet waves
in three.js evolution. Uses hyperframes composition system.
"""
import json, os, shutil, sys, subprocess, time

ROOT = r"C:/æ/fleet-waves-demo"
SCENES = os.path.join(ROOT, "scenes")

# Ensure project structure exists
for d in ["compositions", "compositions/components", "assets"]:
    os.makedirs(os.path.join(ROOT, d), exist_ok=True)

# Copy hyperframes config
hf_json_src = r"C:/æ/cuda-mcp2-demo/hyperframes.json"
hf_json_dst = os.path.join(ROOT, "hyperframes.json")
if os.path.exists(hf_json_src):
    shutil.copy(hf_json_src, hf_json_dst)

# Create index.html — the main composition
INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080">
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { margin: 0; width: 1920px; height: 1080px; overflow: hidden;
        background: #010204; color: #f5f7fa;
        font-family: 'JetBrains Mono', 'Consolas', monospace; }
      #root { width: 100%; height: 100%; position: relative; overflow: hidden; }
      .scanlines { position: absolute; inset: 0; pointer-events: none; z-index: 100;
        background: repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.25) 3px, rgba(0,0,0,0.25) 4px); }
      .neural-mesh { position: absolute; inset: 0; z-index: 1;
        background: radial-gradient(circle at 50% 50%, rgba(0,234,255,0.03) 0%, transparent 70%),
                    radial-gradient(circle at 30% 30%, rgba(212,175,55,0.02) 0%, transparent 50%); }
      .overlay { position: absolute; top: 20px; left: 20px; right: 20px; display: flex;
        justify-content: space-between; align-items: center; z-index: 10; }
      .title { font-size: 36px; color: #00eaff; text-shadow: 0 0 20px rgba(0,234,255,0.4);
        letter-spacing: -0.02em; font-family: 'Space Grotesk', sans-serif; }
      .tag { font-size: 14px; color: rgba(0,234,255,0.4); letter-spacing: 0.2em; }
      .footer { position: absolute; bottom: 20px; left: 20px; right: 20px;
        display: flex; justify-content: space-between; font-size: 12px; color: rgba(212,175,55,0.3); z-index: 10; }
      .timeline-marker { display: flex; align-items: center; gap: 8px; }
      .timeline-dot { width: 8px; height: 8px; border-radius: 50%; background: #D4AF37;
        box-shadow: 0 0 8px #D4AF37; }
      .timeline-dot.active { background: #00ff9d; box-shadow: 0 0 12px #00ff9d; }
      .tech-stack { display: flex; gap: 4px; flex-wrap: wrap; }
      .tech { font-size: 10px; padding: 2px 6px; border: 1px solid rgba(212,175,55,0.3);
        border-radius: 3px; background: rgba(212,175,55,0.08); }
      .stage { position: absolute; inset: 0; z-index: 5; overflow: hidden; }
      .phase { position: absolute; inset: 0; display: flex; flex-direction: column;
        align-items: center; justify-content: center; text-align: center;
        opacity: 0; transform: translateY(20px); transition: all 0.6s ease; }
      .phase.active { opacity: 1; transform: translateY(0); }
      .phase h2 { font-size: 28px; color: #D4AF37; margin-bottom: 12px; font-family: 'Space Grotesk', sans-serif; }
      .phase p { font-size: 14px; color: rgba(212,175,55,0.5); max-width: 600px; line-height: 1.6; }
      .phase .code { font-size: 11px; color: #00eaff; margin-top: 16px;
        background: rgba(5,5,5,0.8); padding: 16px 24px; border-radius: 6px;
        font-family: 'JetBrains Mono', monospace; border: 1px solid rgba(0,234,255,0.2); }
      .fleet-wave { position: absolute; bottom: 0; left: 0; width: 100%; height: 60px;
        display: flex; align-items: flex-end; gap: 2px; padding: 0 4px; z-index: 3; }
      .fleet-bar { width: 4px; height: 0; border-radius: 2px 2px 0 0;
        transition: height 0.4s ease, background-color 0.3s; }
      .fleet-bar.hermes { background: linear-gradient(top, #D4AF37, #f0d487); }
      .fleet-bar.vps { background: linear-gradient(top, #00eaff, #00a8cc); }
      .fleet-bar.teknium { background: linear-gradient(top, #00ff9d, #00cc80); }
      .fleet-label { position: absolute; bottom: 5px; left: 4px; font-size: 8px;
        color: rgba(212,175,55,0.4); letter-spacing: 0.1em; }
      .connection-line { position: absolute; border: 1px solid rgba(0,234,255,0.15);
        z-index: 2; }
    </style>
</head>
<body>
    <div id="root" data-composition-id="fleet-waves" data-start="0" data-duration="22" data-width="1920" data-height="1080">
      <div class="neural-mesh"></div>
      <div class="scanlines"></div>
      <div class="stage" id="stage"></div>

      <!-- Footer with timeline -->
      <div class="footer clip" data-start="0" data-duration="22" data-track-index="3">
        <div class="timeline-marker">
          <span class="timeline-dot" id="dot1" style="background:#00ff9d"></span>
          <span>Phase 1: Particle Field (90k points)</span>
          <span class="timeline-dot" id="dot2"></span>
          <span>Phase 2: Fleet Waves (3 swarms)</span>
          <span class="timeline-dot" id="dot3"></span>
          <span>Phase 3: Shader Orchestration</span>
          <span class="timeline-dot" id="dot4"></span>
          <span>Phase 4: Render Pipeline</span>
        </div>
        <div class="tech-stack">
          <span class="tech">three.js 0.170.0</span>
          <span class="tech">WebGPU</span>
          <span class="tech">ShaderMaterial</span>
          <span class="tech">hyperframes</span>
          <span class="tech">gsap timeline</span>
          <span class="tech">mulberry32 PRNG</span>
        </div>
      </div>
    </div>

    <script>
      const tl = gsap.timeline({ paused: true });

      /* Phase transitions timed to 5.5s each */
      tl.to("#dot1", { backgroundColor: "#D4AF37", boxShadow: "0 0 12px #D4AF37" }, 0);
      tl.to("#phase1", { opacity: 1, y: 0, onStart: () => {
        document.getElementById("dot1").classList.add("active");
      } }, 0.5);

      tl.to("#phase1", { opacity: 0, y: -20 }, 6);
      tl.to("#dot2", { backgroundColor: "#D4AF37", boxShadow: "0 0 12px #D4AF37" }, 6);
      tl.to("#phase2", { opacity: 1, y: 0 }, 6.5);

      tl.to("#phase2", { opacity: 0, y: -20 }, 12);
      tl.to("#dot3", { backgroundColor: "#D4AF37", boxShadow: "0 0 12px #D4AF37" }, 12);
      tl.to("#phase3", { opacity: 1, y: 0 }, 12.5);

      tl.to("#phase3", { opacity: 0, y: -20 }, 18);
      tl.to("#dot4", { backgroundColor: "#D4AF37", boxShadow: "0 0 12px #D4AF37" }, 18);
      tl.to("#phase4", { opacity: 1, y: 0 }, 18.5);
      tl.to(".tech", { color: "#00ff9d" }, 20);

      window.__timelines = window.__timelines || {};
      window.__timelines["fleet-waves"] = tl;
    </script>
</body>
</html>
"""

with open(os.path.join(ROOT, "index.html"), "w") as f:
    f.write(INDEX_HTML)

print("fleet-waves-demo/index.html written")
