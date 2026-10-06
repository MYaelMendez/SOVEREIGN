#!/usr/bin/env python3
"""Simple test server for VSCODER://BRIDGE verification."""
import http.server
import json
import hashlib
import datetime
from pathlib import Path

PORT = 8123
ROOT = Path(__file__).parent

RECEIPT_CHAIN = []

def compute_hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def add_receipt(action, input_data, output_data):
    prev_hash = RECEIPT_CHAIN[-1]["receiptHash"] if RECEIPT_CHAIN else ""
    entry = {
        "seq": len(RECEIPT_CHAIN) + 1,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "action": action,
        "intentHash": hashlib.sha256(input_data[:500].encode()).hexdigest(),
        "planHash": hashlib.sha256(action.encode()).hexdigest(),
        "beforeHash": "",
        "afterHash": hashlib.sha256(output_data[:500].encode()).hexdigest(),
        "tests": {"passed": 0, "failed": 0, "skipped": 0, "details": []},
        "previousReceiptHash": prev_hash,
    }
    entry["receiptHash"] = compute_hash(entry)
    RECEIPT_CHAIN.append(entry)
    return entry

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write((ROOT / "webview" / "index.html").read_text(encoding="utf-8").encode())
        elif self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "version": "1.0.0",
                "tools": ["vscoder_observe", "vscoder_plan", "vscoder_refactor",
                    "vscoder_build", "vscoder_test", "vscoder_debug",
                    "vscoder_benchmark", "vscoder_git_diff", "vscoder_receipt"]
            }).encode())
        elif self.path == "/api/ide-state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "version": "VSCODER_IDE_STATE_V1",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "workspace": {"folders": [], "name": "", "isTrusted": True},
                "active_file": None,
                "open_editors": [],
                "cursor": None,
                "selection": None,
                "visible_ranges": [],
                "diagnostics": [],
                "terminals": [],
                "running_tasks": [],
                "tests": {"controllers": 0, "totalTests": 0},
                "debug_session": {"isActive": False},
                "breakpoints": [],
                "scm_state": {"branch": "unknown", "changes": 0, "repositories": 0},
                "current_branch": "unknown",
                "dirty_files": [],
                "active_panel": None,
                "focused_view": None,
                "mode": "standalone",
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
            cl = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(cl)
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

    def invoke_tool(self, tool, params):
        if tool == "vscoder_observe":
            result = {
                "version": "VSCODER_IDE_STATE_V1",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "workspace": {"folders": [], "name": "", "isTrusted": True},
                "active_file": None,
                "open_editors": [],
                "cursor": None,
                "selection": None,
                "visible_ranges": [],
                "diagnostics": [],
                "terminals": [],
                "running_tasks": [],
                "tests": {"controllers": 0, "totalTests": 0},
                "debug_session": {"isActive": False},
                "breakpoints": [],
                "scm_state": {"branch": "unknown", "changes": 0, "repositories": 0},
                "current_branch": "unknown",
                "dirty_files": [],
                "active_panel": None,
                "focused_view": None,
                "mode": "standalone",
                "authority": {"level": "LOCAL", "reason": "Read-only IDE state observation"},
            }
            add_receipt("observe", json.dumps(params), json.dumps(result))
            return result
        elif tool == "vscoder_plan":
            instruction = params.get("instruction", "optimize workspace")
            result = {
                "instruction": instruction,
                "steps": ["Analyze workspace structure", "Identify optimization targets",
                    "Apply semantic refactoring", "Run tests to verify", "Generate receipt"],
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            }
            add_receipt("plan", instruction, json.dumps(result))
            return result
        elif tool == "vscoder_receipt":
            return {
                "chain": RECEIPT_CHAIN,
                "valid": True,
                "count": len(RECEIPT_CHAIN),
                "latest": RECEIPT_CHAIN[-1] if RECEIPT_CHAIN else None,
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
        pass

if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"VSCODER://BRIDGE test server running on http://localhost:{PORT}")
    server.serve_forever()
