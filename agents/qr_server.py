#!/usr/bin/env python3
"""æ://qr_server — local HTTP server for the QR key/contract infrastructure.

Serves the HTML surface and API endpoints for key management and contract encoding.
Stdlib-only. No framework. Air-gappable.

Contract:
    GET  /                    → qr_keys.html
    GET  /api/key/list        → list keys
    POST /api/key/create      → create key
    POST /api/key/qr-encode   → encode key as QR
    POST /api/key/qr-decode   → decode QR to key
    POST /api/key/sign        → sign message
    POST /api/contract/create → create contract
    POST /api/contract/sign   → sign contract
    POST /api/contract/qr-encode → encode contract as QR
    POST /api/contract/qr-decode → decode QR to contract
    POST /api/contract/execute → execute contract
    GET  /api/ledger          → ledger entries
    GET  /api/status          → server status

Run:  python qr_server.py                 # 127.0.0.1:3051
      python qr_server.py --port 3051
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ══════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════
DEFAULT_HOST = os.environ.get("QR_SERVER_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("QR_SERVER_PORT", "3051"))
KEY_DIR = Path(r"C:\æ\secrets\keys")
QR_DIR = KEY_DIR / "qr"
LEDGER_FILE = Path(r"C:\æ\keeper\ledger.jsonl")
HTML_FILE = Path(r"C:\æ\github-pages\aipodcast_me\qr_keys.html")

# ══════════════════════════════════════════════════════════
# Import QR modules
# ══════════════════════════════════════════════════════════
# Derive from __file__ so this works from any cwd / mount (not just C:\æ\agents).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qr_key_manager import (
    create_key, list_keys, get_key, sign_with_key, verify_signature,
    encode_qr, decode_qr, encode_key_as_qr, decode_qr_to_key
)
from contract_qr import (
    create_contract, sign_contract, verify_contract,
    encode_contract_as_qr, decode_qr_contract, execute_contract,
    reassemble_contract
)

# ══════════════════════════════════════════════════════════
# HTTP Handler
# ══════════════════════════════════════════════════════════

class QRRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for QR infrastructure API."""

    server_version = "æ-qr-server/1.0.0"
    sys_version = ""

    def do_OPTIONS(self):
        """CORS preflight."""
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/" or path == "/qr_keys.html":
                self.serve_html()
            elif path == "/api/status":
                self.send_json({"status": "live", "host": self.client_address[0]})
            elif path == "/api/key/list":
                self.send_json(list_keys())
            elif path == "/api/ledger":
                self.send_json(self.get_ledger())
            else:
                self.send_error(404, f"Unknown endpoint: {path}")
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def do_POST(self):
        """Handle POST requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_json({"error": "invalid JSON"}, status=400)
            return

        try:
            if path == "/api/key/create":
                self.handle_create_key(data)
            elif path == "/api/key/qr-encode":
                self.handle_qr_encode(data)
            elif path == "/api/key/qr-decode":
                self.handle_qr_decode(data)
            elif path == "/api/key/sign":
                self.handle_sign(data)
            elif path == "/api/contract/create":
                self.handle_create_contract(data)
            elif path == "/api/contract/sign":
                self.handle_sign_contract(data)
            elif path == "/api/contract/qr-encode":
                self.handle_contract_qr_encode(data)
            elif path == "/api/contract/qr-decode":
                self.handle_contract_qr_decode(data)
            elif path == "/api/contract/execute":
                self.handle_execute_contract(data)
            else:
                self.send_error(404, f"Unknown endpoint: {path}")
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    # ── HTML serving ──

    def serve_html(self):
        """Serve the QR keys HTML surface."""
        if not HTML_FILE.exists():
            self.send_error(404, f"HTML file not found: {HTML_FILE}")
            return

        self.send_response(200)
        self.send_cors_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_FILE.read_bytes())

    # ── Key endpoints ──

    def handle_create_key(self, data):
        """Create a new key."""
        name = data.get("name", "")
        algorithm = data.get("algorithm", "ed25519")
        if not name:
            self.send_json({"error": "name required"}, status=400)
            return

        result = create_key(name, algorithm)
        if "error" in result:
            self.send_json(result, status=400)
            return

        self.send_json(result)

    def handle_qr_encode(self, data):
        """Encode a key as QR code."""
        name = data.get("name", "")
        if not name:
            self.send_json({"error": "name required"}, status=400)
            return

        key = get_key(name)
        if "error" in key:
            self.send_json(key, status=404)
            return

        # Reconstruct keypair from file for encoding
        key_file = KEY_DIR / f"{name}.key"
        if not key_file.exists():
            self.send_json({"error": f"key file not found: {name}"}, status=404)
            return

        with open(key_file, encoding="utf-8") as f:
            keypair = json.load(f)

        result = encode_key_as_qr(keypair)
        self.send_json(result)

    def handle_qr_decode(self, data):
        """Decode a QR code to key."""
        filepath = data.get("filepath", "")
        if not filepath:
            self.send_json({"error": "filepath required"}, status=400)
            return

        result = decode_qr_to_key(filepath)
        if result is None:
            self.send_json({"error": "no key found in QR"}, status=400)
            return

        self.send_json(result)

    def handle_sign(self, data):
        """Sign a message with a key."""
        name = data.get("name", "")
        message = data.get("message", "")
        if not name or not message:
            self.send_json({"error": "name and message required"}, status=400)
            return

        result = sign_with_key(name, message)
        if "error" in result:
            self.send_json(result, status=404)
            return

        self.send_json(result)

    # ── Contract endpoints ──

    def handle_create_contract(self, data):
        """Create a new contract and save to file."""
        contract_type = data.get("type", "escrow")
        terms = data.get("terms", {})
        parties = data.get("parties", [])
        conditions = data.get("conditions", [])
        actions = data.get("actions", [])

        contract = create_contract(contract_type, terms, parties, conditions, actions)
        if "error" in contract:
            self.send_json(contract, status=400)
            return

        # Save contract to file for later operations
        contract_dir = Path(r"C:\æ\secrets\keys\contracts")
        contract_dir.mkdir(parents=True, exist_ok=True)
        contract_file = contract_dir / f"{contract['hash'][:16]}.json"
        with open(contract_file, 'w', encoding='utf-8') as f:
            json.dump(contract, f, indent=2)

        contract["_file"] = str(contract_file)
        self.send_json(contract)

    def handle_sign_contract(self, data):
        """Sign a contract."""
        contract_file = data.get("contract_file", "")
        private_key = data.get("private_key", "")

        if not contract_file or not private_key:
            self.send_json({"error": "contract_file and private_key required"}, status=400)
            return

        # Load contract from file
        contract_path = Path(contract_file)
        if not contract_path.exists():
            self.send_json({"error": f"contract file not found: {contract_file}"}, status=404)
            return

        with open(contract_path, encoding="utf-8") as f:
            contract = json.load(f)

        contract = sign_contract(contract, private_key)

        # Save updated contract
        with open(contract_path, "w", encoding="utf-8") as f:
            json.dump(contract, f, indent=2)

        self.send_json(contract)

    def handle_contract_qr_encode(self, data):
        """Encode a contract as QR code."""
        contract_file = data.get("contract_file", "")
        filepath = data.get("filepath", None)

        if not contract_file:
            self.send_json({"error": "contract_file required"}, status=400)
            return

        # Load contract from file
        contract_path = Path(contract_file)
        if not contract_path.exists():
            self.send_json({"error": f"contract file not found: {contract_file}"}, status=404)
            return

        with open(contract_path, encoding="utf-8") as f:
            contract = json.load(f)

        result = encode_contract_as_qr(contract, filepath)
        self.send_json(result)

    def handle_contract_qr_decode(self, data):
        """Decode a QR code to contract."""
        filepath = data.get("filepath", "")
        if not filepath:
            self.send_json({"error": "filepath required"}, status=400)
            return

        result = decode_qr_contract(filepath)
        self.send_json(result)

    def handle_execute_contract(self, data):
        """Execute a contract."""
        contract_file = data.get("contract_file", "")
        private_key = data.get("private_key", "")
        public_keys = data.get("public_keys", [])

        if not contract_file or not private_key or not public_keys:
            self.send_json({"error": "contract_file, private_key, and public_keys required"}, status=400)
            return

        # Load contract from file
        contract_path = Path(contract_file)
        if not contract_path.exists():
            self.send_json({"error": f"contract file not found: {contract_file}"}, status=404)
            return

        with open(contract_path, encoding="utf-8") as f:
            contract = json.load(f)

        result = execute_contract(contract, private_key, public_keys)
        self.send_json(result)

    # ── Helpers ──

    def get_ledger(self):
        """Read ledger entries."""
        if not LEDGER_FILE.exists():
            return {"entries": []}

        entries = []
        with open(LEDGER_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        return {"entries": entries}

    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def send_cors_headers(self):
        """Send CORS headers for local access."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        """Custom log format."""
        sys.stderr.write(f"qr_server: {args[0]}\n")


# ══════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="æ://qr_server - local QR infrastructure server")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind")
    args = parser.parse_args()

    host = args.host
    port = args.port

    server = ThreadingHTTPServer((host, port), QRRequestHandler)
    print(f"æ://qr_server listening on {host}:{port}")
    print(f"  HTML surface: http://{host}:{port}/")
    print(f"  API: http://{host}:{port}/api/status")
    print(f"  Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
