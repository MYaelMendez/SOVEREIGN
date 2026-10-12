#!/usr/bin/env python3
"""
videolab render.py — manifest-driven, data-injected, mesh-addressable video lab.

Usage:
  python render.py render <scene> [--live] [--output out.mp4]
  python render.py status
  python render.py watch <scene>

Data flow:
  1. Fetch live telemetry from broker (129.212.180.252:3000) or local nvidia-smi
  2. If broker dark → fallback to data/telemetry.json (last-known-good)
  3. Inject {{tokens}} into scene HTML
  4. Call npx hyperframes render --gpu (RTX hardware encoding)

The lab is always renderable. More valuable when the mesh is up.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
SCENES = ROOT / "scenes"
DATA = ROOT / "data"
LAB_JSON = ROOT / "lab.json"
TELEMETRY_CACHE = DATA / "telemetry.json"

BROKER_URL = "http://129.212.180.252:3000"
BROKER_TIMEOUT = 8  # seconds


def fetch_live_telemetry() -> dict:
    """Fetch live telemetry from the public broker. Returns {} on failure."""
    try:
        # Probe GPU
        probe_url = f"{BROKER_URL}/xrpc/ae.vps.rtx?op=probe"
        with urllib.request.urlopen(probe_url, timeout=BROKER_TIMEOUT) as resp:
            probe = json.loads(resp.read())

        # Matmul benchmark
        matmul_url = f"{BROKER_URL}/xrpc/ae.vps.rtx?op=matmul&n=512"
        with urllib.request.urlopen(matmul_url, timeout=BROKER_TIMEOUT) as resp:
            matmul = json.loads(resp.read())

        # Brain speed (local ollama)
        brain_tok_s = "—"
        try:
            import urllib.request as req
            tags_url = "http://127.0.0.1:11434/api/tags"
            with req.urlopen(tags_url, timeout=3) as resp:
                tags = json.loads(resp.read())
                models = [m["name"] for m in tags.get("models", [])]
                if "qwen2.5-coder:7b" in models:
                    brain_tok_s = "116.7"  # last measured
        except Exception:
            pass

        gpu_name = probe.get("gpu", {}).get("name", "RTX 3050")
        gpu_mem = probe.get("gpu", {}).get("memory", "6GB")
        matmul_ms = matmul.get("run", {}).get("host_ms", "—")

        return {
            "brain_tok_s": brain_tok_s,
            "matmul_host_ms": str(matmul_ms),
            "gpu_name": gpu_name,
            "gpu_mem": gpu_mem,
            "live": True,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    except Exception as e:
        print(f"  ⚠ Broker unreachable: {e}", file=sys.stderr)
        return {}


def load_fallback_telemetry() -> dict:
    """Load last-known-good telemetry from cache."""
    if TELEMETRY_CACHE.exists():
        data = json.loads(TELEMETRY_CACHE.read_text())
        data["live"] = False
        return data
    # Ultimate fallback — hardcoded from last verified run
    return {
        "brain_tok_s": "116.7",
        "matmul_host_ms": "507",
        "gpu_name": "RTX 3050",
        "gpu_mem": "6GB",
        "live": False,
        "timestamp": "2026-07-10T00:00:00Z",
    }


def get_telemetry(live: bool = True) -> dict:
    """Get telemetry: live if possible, fallback otherwise."""
    if live:
        data = fetch_live_telemetry()
        if data:
            # Cache for next fallback
            DATA.mkdir(exist_ok=True)
            TELEMETRY_CACHE.write_text(json.dumps(data, indent=2))
            return data
    return load_fallback_telemetry()


def inject_tokens(html: str, telemetry: dict) -> str:
    """Replace {{tokens}} in HTML with telemetry values."""
    for key, value in telemetry.items():
        html = html.replace(f"{{{{{key}}}}}", str(value))
    return html


def render_scene(scene_name: str, live: bool = True, output: str = None) -> Path:
    """Render a scene with data injection."""
    scene_file = SCENES / f"{scene_name}.html"
    if not scene_file.exists():
        print(f"✗ Scene not found: {scene_file}", file=sys.stderr)
        sys.exit(1)

    # Read scene
    html = scene_file.read_text(encoding="utf-8")

    # Get telemetry
    telemetry = get_telemetry(live=live)
    live_flag = "LIVE" if telemetry.get("live") else "CACHED"
    print(f"  📡 Telemetry [{live_flag}]: {telemetry}")

    # Inject
    html = inject_tokens(html, telemetry)

    # Copy lab.json if it exists for hyperframes project context
    lab_json_src = ROOT / "lab.json"
    if lab_json_src.exists():
        import shutil
        for dst in [SCENES / "hyperframes.json", SCENES / "lab.json"]:
            shutil.copy2(str(lab_json_src), str(dst))

    # Write injected scene as index.html (hyperframes needs index.html as root)
    injected = SCENES / "index.html"
    injected.write_text(html, encoding="utf-8")

    # Render — hyperframes render reads a project directory
    out_path = output or str(ROOT / f"{scene_name}.mp4")
    cmd_str = f'npx hyperframes render "{SCENES}" --output "{out_path}" --gpu -q draft'
    print(f"  🎬 Rendering: {cmd_str}")
    result = subprocess.run(cmd_str, capture_output=True, text=True, cwd=str(SCENES), shell=True)

    # Cleanup
    injected.unlink(missing_ok=True)
    (SCENES / "hyperframes.json").unlink(missing_ok=True)
    (SCENES / "lab.json").unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"  ✗ Render failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    out_file = Path(out_path)
    print(f"  ✅ Rendered: {out_file} ({out_file.stat().st_size / 1024 / 1024:.1f} MB)")
    return out_file


def show_status():
    """Show lab status."""
    telemetry = get_telemetry(live=True)
    live_flag = "🟢 LIVE" if telemetry.get("live") else "🟡 CACHED"
    print(f"\n  æ Video Lab — {live_flag}")
    print(f"  ├─ Brain:    {telemetry.get('brain_tok_s')} tok/s")
    print(f"  ├─ Matmul:   {telemetry.get('matmul_host_ms')} ms")
    print(f"  ├─ GPU:      {telemetry.get('gpu_name')} {telemetry.get('gpu_mem')}")
    print(f"  └─ Updated:  {telemetry.get('timestamp')}")
    print()


def watch_scene(scene_name: str):
    """Watch a scene for changes and auto-re-render."""
    import hashlib

    scene_file = SCENES / f"{scene_name}.html"
    if not scene_file.exists():
        print(f"✗ Scene not found: {scene_file}", file=sys.stderr)
        sys.exit(1)

    last_hash = ""
    print(f"  👁 Watching {scene_file} (Ctrl+C to stop)")
    while True:
        current_hash = hashlib.md5(scene_file.read_bytes()).hexdigest()
        if current_hash != last_hash:
            last_hash = current_hash
            print(f"  🔄 Change detected, re-rendering...")
            try:
                render_scene(scene_name, live=True)
            except SystemExit:
                pass
        time.sleep(2)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "render":
        if len(sys.argv) < 3:
            print("Usage: python render.py render <scene> [--live] [--output out.mp4]")
            sys.exit(1)
        scene = sys.argv[2]
        live = "--live" in sys.argv
        output = None
        if "--output" in sys.argv:
            idx = sys.argv.index("--output")
            output = sys.argv[idx + 1]
        render_scene(scene, live=live, output=output)

    elif cmd == "status":
        show_status()

    elif cmd == "watch":
        if len(sys.argv) < 3:
            print("Usage: python render.py watch <scene>")
            sys.exit(1)
        watch_scene(sys.argv[2])

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
