#!/usr/bin/env python3
"""VSCODER:// HTTP server — serves the WebMCP interface on :8123"""
import http.server
import os
import json
import hashlib
import datetime
from pathlib import Path

PORT = 8123
ROOT = Path(__file__).parent

# In-memory receipt chain for standalone mode
RECEIPT_CHAIN = []

def compute_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()

def add_receipt(action: str, input_data: str, output_data: str) -> dict:
    prev_hash = RECEIPT_CHAIN[-1]["hash"] if RECEIPT_CHAIN else "genesis"
    entry = {
        "seq": len(RECEIPT_CHAIN) + 1,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "action": action,
        "input": input_data[:500],
        "output": output_data[:500],
        "prevHash": prev_hash,
    }
    entry["hash"] = compute_hash(entry)
    RECEIPT_CHAIN.append(entry)
    return entry

class VSCODERHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = (ROOT / "webview" / "index.html").read_text(encoding="utf-8")
            self.wfile.write(html.encode())
        elif self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "version": "0.1.0",
                "tools": [
                    "vscoder_observe", "vscoder_plan", "vscoder_refactor",
                    "vscoder_build", "vscoder_test", "vscoder_debug",
                    "vscoder_benchmark", "vscoder_git_diff", "vscoder_receipt"
                ]
            }).encode())
        elif self.path == "/api/receipts":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "chain": RECEIPT_CHAIN,
                "valid": True,
                "count": len(RECEIPT_CHAIN),
            }).encode())
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/invoke":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                tool = data.get("tool", "")
                params = data.get("params", {})
                result = self.invoke_tool(tool, params)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def invoke_tool(self, tool: str, params: dict) -> dict:
        if tool == "vscoder_observe":
            result = {
                "workspace": [],
                "editors": [],
                "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                "mode": "standalone",
            }
            add_receipt("observe", json.dumps(params), json.dumps(result))
            return result
        elif tool == "vscoder_plan":
            instruction = params.get("instruction", "optimize workspace")
            result = {
                "instruction": instruction,
                "steps": [
                    "Analyze workspace structure",
                    "Identify optimization targets",
                    "Apply semantic refactoring",
                    "Run tests to verify",
                    "Generate receipt",
                ],
                "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            }
            add_receipt("plan", instruction, json.dumps(result))
            return result
        elif tool == "vscoder_receipt":
            return {
                "chain": RECEIPT_CHAIN,
                "valid": True,
                "count": len(RECEIPT_CHAIN),
                "last": RECEIPT_CHAIN[-1] if RECEIPT_CHAIN else None,
            }
        elif tool == "vscoder_git_diff":
            result = {"mode": "standalone", "hasChanges": False, "diff": "", "status": ""}
            add_receipt("git_diff", json.dumps(params), json.dumps(result))
            return result
        elif tool == "vscoder_build":
            result = {"mode": "standalone", "success": True, "output": "Build completed (standalone mode)"}
            add_receipt("build", json.dumps(params), json.dumps(result))
            return result
        elif tool == "vscoder_test":
            result = {"mode": "standalone", "success": True, "output": "Tests passed (standalone mode)"}
            add_receipt("test", json.dumps(params), json.dumps(result))
            return result
        elif tool == "vscoder_benchmark":
            result = {"mode": "standalone", "success": True, "metrics": {"latencyP50": 0, "latencyP95": 0, "fps": 0}}
            add_receipt("benchmark", json.dumps(params), json.dumps(result))
            return result
        elif tool == "vscoder_debug":
            result = {"mode": "standalone", "success": True, "message": "Debug session started (standalone mode)"}
            add_receipt("debug", json.dumps(params), json.dumps(result))
            return result
        elif tool == "vscoder_refactor":
            result = {"mode": "standalone", "kind": params.get("kind", "rename"), "applied": False}
            add_receipt("refactor", json.dumps(params), json.dumps(result))
            return result
        else:
            return {"error": f"Unknown tool: {tool}"}

    def log_message(self, format, *args):
        pass  # Suppress default logging

if __name__ == "__main__":
    import datetime  # noqa: F811
    server = http.server.HTTPServer(("0.0.0.0", PORT), VSCODERHandler)
    print(f"VSCODER:// server running on http://localhost:{PORT}")
    server.serve_forever()