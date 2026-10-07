#!/usr/bin/env python3
"""CRI:// API server — Consumer Redline Index HTTP server.

Extends the local API pattern for economic index calculations.
Serves the CRI surface and API endpoints.

Contract:
    GET  /                    → cri_surface.html
    GET  /api/status          → server status
    GET  /api/cri/current     → current CRI release
    GET  /api/cri/history     → release history
    POST /api/cri/calculate   → calculate CRI from observations
    POST /api/cri/release     → create new release
    POST /api/cri/explain     → explain CRI decomposition
    GET  /api/sources         → source registry
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone

# ══════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════
DEFAULT_HOST = os.environ.get("CRI_SERVER_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("CRI_SERVER_PORT", "3052"))
CRI_DIR = Path(r"C:\æ\cri")
RELEASES_DIR = CRI_DIR / "data" / "releases"
SURFACE_FILE = Path(r"C:\æ\github-pages\aipodcast_me\cri_surface.html")

# ══════════════════════════════════════════════════════════
# Import CRI engine
# ══════════════════════════════════════════════════════════
# Derive from __file__ so this works from any cwd / mount (not just C:\æ\agents).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cri_engine import (
    Observation, CRICalculator, ExplainabilityEngine, Release,
    SOURCE_REGISTRY, COMPONENT_FAMILIES
)

# ══════════════════════════════════════════════════════════
# HTTP Handler
# ══════════════════════════════════════════════════════════

class CRIRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for CRI infrastructure API."""

    server_version = "æ-cri-server/1.0.0"
    sys_version = ""

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/" or path == "/cri_surface.html":
                self.serve_surface()
            elif path == "/api/status":
                self.send_json({"status": "live", "host": self.client_address[0]})
            elif path == "/api/cri/current":
                self.handle_current_cri()
            elif path == "/api/cri/history":
                self.handle_history()
            elif path == "/api/sources":
                self.send_json({"sources": SOURCE_REGISTRY})
            else:
                self.send_error(404, f"Unknown endpoint: {path}")
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_json({"error": "invalid JSON"}, status=400)
            return

        try:
            if path == "/api/cri/calculate":
                self.handle_calculate(data)
            elif path == "/api/cri/release":
                self.handle_release(data)
            elif path == "/api/cri/explain":
                self.handle_explain(data)
            else:
                self.send_error(404, f"Unknown endpoint: {path}")
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    # ── Surface serving ──

    def serve_surface(self):
        """Serve the CRI surface HTML."""
        if not SURFACE_FILE.exists():
            # Fallback: return minimal surface
            self.send_response(200)
            self.send_cors_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>CRI:// Consumer Redline Index</title>
<style>body{background:#050505;color:#E8E0D0;font-family:monospace;padding:20px;max-width:430px;margin:0 auto}
h1{color:#D4AF37;font-family:Orbitron,sans-serif;font-size:18px}
.pill{display:inline-block;padding:4px 8px;border:1px solid #D4AF37;border-radius:4px;font-size:10px;margin:2px}
.live{background:#4CAF50;color:#000}.warn{background:#D4AF37;color:#000}</style>
</head><body>
<h1>CRI://</h1>
<p>Consumer Redline Index</p>
<p><span class="pill warn">API ACTIVE</span></p>
<p>Surface loading...</p>
</body></html>"""
            self.wfile.write(html.encode())
            return

        self.send_response(200)
        self.send_cors_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(SURFACE_FILE.read_bytes())

    # ── CRI endpoints ──

    def handle_current_cri(self):
        """Get current CRI release."""
        if not RELEASES_DIR.exists():
            self.send_json({"error": "no releases yet"}, status=404)
            return

        release_files = sorted(RELEASES_DIR.glob("*.json"))
        if not release_files:
            self.send_json({"error": "no releases yet"}, status=404)
            return

        with open(release_files[-1], encoding="utf-8") as f:
            release = json.load(f)

        self.send_json(release)

    def handle_history(self):
        """Get release history."""
        if not RELEASES_DIR.exists():
            self.send_json({"releases": []})
            return

        releases = []
        for filepath in sorted(RELEASES_DIR.glob("*.json")):
            try:
                with open(filepath, encoding="utf-8") as f:
                    release = json.load(f)
                releases.append({
                    "as_of": release.get("as_of"),
                    "cri_score": release.get("cri_score"),
                    "status": release.get("status"),
                    "release_hash": release.get("release_hash"),
                    "previous_release_hash": release.get("previous_release_hash"),
                })
            except json.JSONDecodeError:
                pass

        self.send_json({"releases": releases})

    def handle_calculate(self, data):
        """Calculate CRI from observations."""
        observations_data = data.get("observations", [])
        history = data.get("history", {})

        observations = []
        for obs_data in observations_data:
            obs = Observation(
                indicator_id=obs_data.get("indicator_id", ""),
                value=obs_data.get("value", 0),
                observation_date=obs_data.get("observation_date", ""),
                release_date=obs_data.get("release_date", ""),
                retrieved_at=obs_data.get("retrieved_at", ""),
                unit=obs_data.get("unit", ""),
                frequency=obs_data.get("frequency", ""),
                vintage=obs_data.get("vintage", 1),
                source_reference=obs_data.get("source_reference", ""),
                producer_hash=obs_data.get("producer_hash", ""),
            )
            observations.append(obs)

        calculator = CRICalculator()
        result = calculator.calculate(observations, history)
        self.send_json(result)

    def handle_release(self, data):
        """Create a new CRI release."""
        observations_data = data.get("observations", [])
        previous_hash = data.get("previous_release_hash", "")

        observations = []
        for obs_data in observations_data:
            obs = Observation(
                indicator_id=obs_data.get("indicator_id", ""),
                value=obs_data.get("value", 0),
                observation_date=obs_data.get("observation_date", ""),
                release_date=obs_data.get("release_date", ""),
                retrieved_at=obs_data.get("retrieved_at", ""),
                unit=obs_data.get("unit", ""),
                frequency=obs_data.get("frequency", ""),
                vintage=obs_data.get("vintage", 1),
                source_reference=obs_data.get("source_reference", ""),
                producer_hash=obs_data.get("producer_hash", ""),
            )
            observations.append(obs)

        # Load previous release hash if not provided
        if not previous_hash and RELEASES_DIR.exists():
            release_files = sorted(RELEASES_DIR.glob("*.json"))
            if release_files:
                with open(release_files[-1], encoding="utf-8") as f:
                    prev = json.load(f)
                previous_hash = prev.get("release_hash", "")

        # Calculate CRI
        history = data.get("history", {})
        calculator = CRICalculator()
        calc_result = calculator.calculate(observations, history)

        # Create release
        release = Release(
            cri_score=calc_result["cri_score"],
            components=calc_result["components"],
            coverage=calc_result["coverage"],
            freshness=calc_result["freshness"],
            status=calc_result["status"],
            observations=observations,
            formula_version=calculator.formula_version,
            weights_version=calculator.weights_version,
            previous_release_hash=previous_hash,
        )

        # Save release
        RELEASES_DIR.mkdir(parents=True, exist_ok=True)
        release_file = RELEASES_DIR / f"cri_{release.as_of}.json"
        with open(release_file, 'w', encoding='utf-8') as f:
            f.write(release.to_json())

        self.send_json(release.to_dict())

    def handle_explain(self, data):
        """Explain CRI decomposition."""
        previous_file = data.get("previous_release_file", "")
        current_file = data.get("current_release_file", "")

        # Load releases
        if previous_file and Path(previous_file).exists():
            with open(previous_file, encoding="utf-8") as f:
                previous = json.load(f)
        else:
            # Load previous release from history
            if RELEASES_DIR.exists():
                release_files = sorted(RELEASES_DIR.glob("*.json"))
                if len(release_files) >= 2:
                    with open(release_files[-2], encoding="utf-8") as f:
                        previous = json.load(f)
                else:
                    self.send_json({"error": "need at least 2 releases"}, status=400)
                    return
            else:
                self.send_json({"error": "no release history"}, status=400)
                return

        if current_file and Path(current_file).exists():
            with open(current_file, encoding="utf-8") as f:
                current = json.load(f)
        else:
            # Load current release from history
            if RELEASES_DIR.exists():
                release_files = sorted(RELEASES_DIR.glob("*.json"))
                if release_files:
                    with open(release_files[-1], encoding="utf-8") as f:
                        current = json.load(f)
                else:
                    self.send_json({"error": "no current release"}, status=400)
                    return
            else:
                self.send_json({"error": "no release history"}, status=400)
                return

        engine = ExplainabilityEngine()
        decomposition = engine.decompose(previous, current)
        explanation = engine.explain([], decomposition)

        self.send_json({
            "decomposition": decomposition,
            "explanation": explanation,
        })

    # ── Helpers ──

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        sys.stderr.write(f"cri_server: {args[0]}\n")


# ══════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CRI:// API server")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port")
    args = parser.parse_args()

    host = args.host
    port = args.port

    server = ThreadingHTTPServer((host, port), CRIRequestHandler)
    print(f"CRI:// server listening on {host}:{port}")
    print(f"  Surface: http://{host}:{port}/")
    print(f"  API: http://{host}:{port}/api/status")
    print(f"  Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
