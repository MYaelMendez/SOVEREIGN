#!/usr/bin/env python3
"""opensourceware media studio — pipeline orchestrator.

Runs the full sovereign video pipeline:
  spec → render → gate → VLC → deploy

Usage:
  python studio.py spec-draw-video.json output/draw-video.mp4
  python studio.py spec-draw-video.json output/draw-video.mp4 --vlc
  python studio.py spec-draw-video.json output/draw-video.mp4 --deploy
  python studio.py spec-draw-video.json output/draw-video.mp4 --all
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.parse
import base64
from pathlib import Path

# ── config ───────────────────────────────────────────────────────────────────

STUDIO = Path(__file__).resolve().parent
REPO = STUDIO.parent
SCENES = STUDIO / "scenes"
SPECS = STUDIO / "specs"
OUTPUT = STUDIO / "output"
GITHUB_PAGES = REPO / "github-pages"

VLC_HTTP = "http://127.0.0.1:8081/requests/status.json"
VLC_PASS = "hermes"

FFPROBE = Path.home() / "AppData" / "Local" / "hermes" / "tools" / "ffmpeg-7.1-nvenc" / "bin" / "ffprobe.exe"

# ── helpers ──────────────────────────────────────────────────────────────────

def _vlc_req(cmd: str, params: dict | None = None) -> dict:
    qs = ""
    if params:
        qs = "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"http://127.0.0.1:8081/requests/{cmd}{qs}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Basic " + base64.b64encode(f":{VLC_PASS}".encode()).decode())
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = resp.read()
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return {"raw": data.decode("utf-8", errors="replace")}


def _receipt(action: str, result: dict) -> dict:
    ts = time.time()
    payload = json.dumps({"action": action, "result": result, "ts": ts}, sort_keys=True)
    return {"action": action, "ts": ts, "sha256": hashlib.sha256(payload.encode()).hexdigest(), "result": result}


def load_spec(name: str) -> dict:
    path = SPECS / name if name.endswith(".json") else SPECS / f"spec-{name}.json"
    with open(path) as f:
        return json.load(f)


def render(spec_path: Path, output_path: Path) -> dict:
    """Run vidaeo-producer.js."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "C:/Users/yaelm/AppData/Local/hermes/tools/node-26.7.0-win32-x64/node.exe",
            str(REPO / "store/mp4-factory-app/vidaeo-producer.js"),
            str(spec_path),
            str(output_path),
        ],
        capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr[-300:]}
    size = output_path.stat().st_size if output_path.exists() else 0
    return {"ok": True, "path": str(output_path), "size": size}


def gate(video_path: Path) -> dict:
    """Run supervisionvidaeo:// verify."""
    proc = subprocess.run(
        [str(REPO / "vidæo/vidæo.py"), "verify", str(video_path)],
        capture_output=True, text=True, timeout=60,
    )
    return {"ok": "PASS" in proc.stdout, "stdout": proc.stdout[-500:]}


def vlc_open(video_path: Path) -> dict:
    """Open video in VLC with gate verification."""
    path_str = str(video_path).replace("\\", "/")
    uri = "file://" + urllib.parse.quote(path_str, safe="/:")
    _vlc_req("status", {"command": "pl_empty"})
    _vlc_req("status", {"command": "in_play", "input": uri})
    time.sleep(2)
    d = _vlc_req("status")
    state = d.get("state")
    fn = d.get("information", {}).get("category", {}).get("meta", {}).get("filename")
    ok = bool(fn) and state in ("playing", "paused")
    return _receipt("vlc_open", {"path": path_str, "state": state, "filename": fn, "ok": ok})


def deploy(video_path: Path) -> dict:
    """Copy to github-pages."""
    dest = GITHUB_PAGES / video_path.name
    import shutil
    shutil.copy2(video_path, dest)
    size = dest.stat().st_size if dest.exists() else 0
    return {"ok": True, "path": str(dest), "size": size}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python studio.py <spec> [output.mp4] [--vlc] [--deploy] [--all]")
        sys.exit(1)

    spec_name = sys.argv[1]
    out_name = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else spec_name.replace("spec-", "").replace(".json", "") + ".mp4"
    output_path = OUTPUT / out_name
    do_vlc = "--vlc" in sys.argv or "--all" in sys.argv
    do_deploy = "--deploy" in sys.argv or "--all" in sys.argv

    print(f"🎬 opensourceware media studio")
    print(f"   spec:   {spec_name}")
    print(f"   output: {output_path}")
    print()

    # 1. Load spec
    spec = load_spec(spec_name)
    print(f"📋 spec loaded: {len(spec)} keys")

    # 2. Render
    print("🎨 rendering…")
    r = render(SPECS / spec_name if spec_name.endswith(".json") else Path(spec_name), output_path)
    if not r["ok"]:
        print(f"   ❌ render failed: {r['error']}")
        sys.exit(1)
    print(f"   ✅ {r['size']} bytes")

    # 3. Gate
    print("🛡️  gate…")
    g = gate(output_path)
    if not g["ok"]:
        print(f"   ❌ gate failed")
        sys.exit(1)
    print(f"   ✅ PASS")

    # 4. Receipt
    receipt = _receipt("pipeline", {"spec": spec_name, "output": str(output_path), "size": r["size"]})
    print(f"📜 receipt: {receipt['sha256'][:16]}…")

    # 5. VLC
    if do_vlc:
        print("▶️  VLC pane…")
        v = vlc_open(output_path)
        print(f"   {'✅' if v['result']['ok'] else '❌'} {v['result'].get('state')}")

    # 6. Deploy
    if do_deploy:
        print("🚀 deploy…")
        d = deploy(output_path)
        print(f"   ✅ {d['path']} ({d['size']} bytes)")

    # 7. Final receipt
    final = sha256(output_path)
    print(f"\n🏁 done: {output_path.name} · {r['size']} bytes · sha256:{final[:16]}…")


if __name__ == "__main__":
    main()
