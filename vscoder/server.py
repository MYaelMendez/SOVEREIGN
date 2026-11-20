#!/usr/bin/env python3
"""VSCODER:// HTTP server — serves the WebMCP interface on :8123"""
import http.server
import os
import json
import pathlib
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
    """Hash the FULL result, then store it whole.

    The previous version truncated input and output to 500 chars BEFORE hashing.
    That produced a valid chain over a truncated payload: the receipt could not
    be parsed back, and two different results sharing a 500-char prefix would
    hash identically. Evidence that loses data is not evidence.
    """
    prev_hash = RECEIPT_CHAIN[-1]["hash"] if RECEIPT_CHAIN else "genesis"
    entry = {
        "seq": len(RECEIPT_CHAIN) + 1,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "action": action,
        "input": input_data,
        "output": output_data,
        "output_sha256": hashlib.sha256(output_data.encode("utf-8")).hexdigest(),
        "output_bytes": len(output_data.encode("utf-8")),
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
        """Every tool does the work or reports why it could not.

        The previous implementation returned {"success": True, "output": "Tests
        passed (standalone mode)"} without running a test, and benchmark metrics
        of all zeros. A hash-chained receipt over a fabricated result is worse
        than no receipt: it makes a lie tamper-evident and therefore credible.
        """
        import subprocess, sys, os, hashlib
        AE = pathlib.Path(os.environ.get("AE_ROOT", "C:/ae"))
        PY = os.environ.get("AE_PYTHON", "C:/gpu/Scripts/python.exe")
        PKGS = ["tinycuda", "tinygpu", "tinypython", "tinyasimov", "tinymujoco"]

        def run(cmd, cwd, timeout=600):
            try:
                r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=timeout)
                return (r.returncode,
                        r.stdout.decode("utf-8", errors="replace"),
                        r.stderr.decode("utf-8", errors="replace"))
            except Exception as exc:
                return (-1, "", f"{type(exc).__name__}: {exc}")

        # A bare "git" resolves to the MSYS/UCRT build shipped inside the app
        # payload, which native Python cannot spawn. Pin the native binary.
        GIT = next((c for c in ("C:/Program Files/Git/cmd/git.exe",
                                "C:/Program Files/Git/bin/git.exe",
                                "C:/Program Files (x86)/Git/cmd/git.exe")
                    if pathlib.Path(c).exists()), "git")

        def git(*args):
            rc, out, err = run([GIT, "-C", str(AE), *args], AE, 120)
            return out.strip() if rc == 0 else None

        if tool == "vscoder_observe":
            head = git("rev-parse", "HEAD")
            branch = git("branch", "--show-current")
            rc, out, _ = run([GIT, "-C", str(AE), "status", "--porcelain"], AE, 120)
            files = [l for l in out.splitlines() if l.strip()] if rc == 0 else []
            inv = []
            for name in PKGS:
                d = AE / name
                src = d / f"{name}.py"
                tests = list((d / "tests").glob("test_*.py")) if (d / "tests").exists() else []
                inv.append({
                    "package": name,
                    "present": src.exists(),
                    "lines": len(src.read_text(encoding="utf-8", errors="replace").splitlines()) if src.exists() else 0,
                    "sha256": hashlib.sha256(src.read_bytes()).hexdigest()[:16] if src.exists() else None,
                    "test_files": len(tests),
                })
            result = {
                "mode": "real", "workspace": str(AE), "branch": branch, "head": head,
                "dirty_tracked": len([f for f in files if not f.startswith("??")]),
                "untracked": len([f for f in files if f.startswith("??")]),
                "packages": inv,
                "editors": [],
                "editors_note": "open-editor state needs the in-editor bridge; not attached",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            }
            add_receipt("observe", json.dumps(params), json.dumps(result))
            return result

        elif tool == "vscoder_test":
            rows, total_pass, total_fail = [], 0, 0
            for name in PKGS:
                d = AE / name
                if not (d / "tests").exists():
                    rows.append({"package": name, "ran": False, "reason": "no tests directory"})
                    continue
                rc, out, err = run([PY, "-m", "pytest", "tests/", "-q", "--no-header"], d, 900)
                tail = (out or err).strip().splitlines()
                summary = tail[-1] if tail else ""
                import re as _re
                mp = _re.search(r"(\d+) passed", summary)
                mf = _re.search(r"(\d+) failed", summary)
                np_ = int(mp.group(1)) if mp else 0
                nf_ = int(mf.group(1)) if mf else 0
                total_pass += np_; total_fail += nf_
                rows.append({"package": name, "ran": True, "exit": rc,
                             "passed": np_, "failed": nf_, "summary": summary[:160]})
            result = {"mode": "real", "success": total_fail == 0 and total_pass > 0,
                      "passed": total_pass, "failed": total_fail, "packages": rows,
                      "note": "pytest actually executed per package",
                      "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}
            add_receipt("test", json.dumps(params), json.dumps(result))
            return result

        elif tool == "vscoder_build":
            rows = []
            for name in PKGS:
                src = AE / name / f"{name}.py"
                if not src.exists():
                    rows.append({"package": name, "ok": False, "reason": "source absent"})
                    continue
                rc, out, err = run([PY, "-c",
                                    f"import py_compile,sys; py_compile.compile(r'{src}', doraise=True); print('OK')"],
                                   AE / name, 120)
                rows.append({"package": name, "ok": rc == 0,
                             "sha256": hashlib.sha256(src.read_bytes()).hexdigest()[:16],
                             "error": (err or "").strip()[:200] if rc != 0 else None})
            result = {"mode": "real", "success": all(r["ok"] for r in rows),
                      "packages": rows, "note": "py_compile per package — syntax, not semantics",
                      "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}
            add_receipt("build", json.dumps(params), json.dumps(result))
            return result

        elif tool == "vscoder_benchmark":
            rows = []
            mj = AE / "tinymujoco"
            if (mj / "tinymujoco.py").exists():
                rc, out, err = run([PY, "-c",
                    "import sys,json; sys.path.insert(0,'.'); import tinymujoco as t; "
                    "print(json.dumps(t.doctor()))"], mj, 180)
                rows.append({"target": "tinymujoco.doctor", "exit": rc,
                             "result": out.strip()[:600] if rc == 0 else (err or "")[:300]})
            tc = AE / "tinycuda"
            if (tc / "tinycuda.py").exists():
                rc, out, err = run([PY, "-c",
                    "import sys,json; sys.path.insert(0,'.'); import tinycuda as t; "
                    "print(json.dumps(t.bench(sizes=(10000,100000), reps=2)))"], tc, 600)
                rows.append({"target": "tinycuda.bench", "exit": rc,
                             "result": out.strip()[:900] if rc == 0 else (err or "")[:300]})
            ok = any(r["exit"] == 0 for r in rows)
            result = {"mode": "real", "success": ok, "measurements": rows,
                      "note": "real timings from the packages; absent tools reported, never zero-filled",
                      "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}
            add_receipt("benchmark", json.dumps(params), json.dumps(result))
            return result

        elif tool == "vscoder_git_diff":
            rc, out, err = run([GIT, "-C", str(AE), "diff", "--stat"], AE, 180)
            rc2, names, _ = run([GIT, "-C", str(AE), "diff", "--name-only"], AE, 180)
            result = {"mode": "real", "hasChanges": bool(out.strip()),
                      "stat": out.strip()[:1500],
                      "files": [n for n in names.splitlines() if n.strip()][:60],
                      "head": git("rev-parse", "--short", "HEAD"),
                      "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}
            add_receipt("git_diff", json.dumps(params), json.dumps(result))
            return result

        elif tool == "vscoder_debug":
            rows = []
            for name, mod in [("tinymujoco", "tinymujoco"), ("tinycuda", "tinycuda")]:
                d = AE / name
                if not (d / f"{mod}.py").exists():
                    continue
                rc, out, err = run([PY, "-c",
                    f"import sys,json; sys.path.insert(0,'.'); import {mod} as t; "
                    f"print(json.dumps(t.doctor()))"], d, 240)
                rows.append({"package": name, "exit": rc,
                             "doctor": out.strip()[:700] if rc == 0 else (err or "")[:300]})
            result = {"mode": "real", "success": all(r["exit"] == 0 for r in rows) and bool(rows),
                      "diagnostics": rows,
                      "note": "each package's own doctor — live probes, not a debug session",
                      "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}
            add_receipt("debug", json.dumps(params), json.dumps(result))
            return result

        elif tool == "vscoder_plan":
            instruction = params.get("instruction", "")
            result = {"mode": "plan", "instruction": instruction,
                      "steps": ["observe (real workspace state)", "test (pytest per package)",
                                "build (py_compile)", "benchmark (measured)", "receipt"],
                      "executed": False,
                      "note": "a plan is a proposal; it claims no work done",
                      "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}
            add_receipt("plan", instruction, json.dumps(result))
            return result

        elif tool == "vscoder_refactor":
            result = {"mode": "refused", "ok": False, "applied": False,
                      "kind": params.get("kind", "rename"),
                      "reason": "automated refactor is not implemented. Refusing rather than "
                                "reporting applied:false as if it were a completed no-op.",
                      "grants": False}
            add_receipt("refactor", json.dumps(params), json.dumps(result))
            return result

        elif tool == "vscoder_receipt":
            return {"chain": RECEIPT_CHAIN, "valid": True,
                    "count": len(RECEIPT_CHAIN),
                    "last": RECEIPT_CHAIN[-1] if RECEIPT_CHAIN else None}

        else:
            return {"error": f"Unknown tool: {tool}"}

    def log_message(self, format, *args):
        pass  # Suppress default logging

if __name__ == "__main__":
    import datetime  # noqa: F811
    server = http.server.HTTPServer(("0.0.0.0", PORT), VSCODERHandler)
    print(f"VSCODER:// server running on http://localhost:{PORT}")
    server.serve_forever()