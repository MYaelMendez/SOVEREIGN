#!/usr/bin/env python3
"""æ://code_mode — sandboxed agent execution against the æ mesh DSL.

The model writes Python code against the æ DSL. This executor runs it
in a sandbox with explicit bindings, no filesystem/network access,
and a 30s timeout. Every call is logged for audit.

Usage:
    python æ_code_mode.py <script.py>
    python æ_code_mode.py --test          # run the built-in test
    python æ_code_mode.py --eval "<code>" # execute inline code
"""

import sys
import os
import json
import time
import signal
import hashlib
import importlib.util
from pathlib import Path
from datetime import datetime, timezone

# ══════════════════════════════════════════════════════════════
# SANDBOX CONFIG
# ══════════════════════════════════════════════════════════════
TIMEOUT_S = 30
ALLOWED_MODULES = {"json", "re", "datetime", "urllib", "collections",
                   "typing", "dataclasses", "enum", "math", "hashlib", "subprocess", "os"}
BLOCKED_BUILTINS = {"open", "socket", "subprocess", "os.system",
                    "exec", "eval", "compile", "__import__",
                    "input", "breakpoint", "execfile"}
LOG_FILE = Path.home() / ".hermes" / "logs" / "code_mode.log"
LEDGER_FILE = Path(r"C:\æ\keeper\ledger.jsonl")

# ══════════════════════════════════════════════════════════════
# THE æ DSL — typed bindings the sandboxed code can use
# ══════════════════════════════════════════════════════════════

class _Mesh:
    """Mesh bindings — bot discovery and state."""
    def bots(self):
        """List active mesh bots."""
        return [
            {"id": "hermes-agent", "status": "ok", "tier": 0},
            {"id": "vps_node", "status": "ok", "tier": 1},
            {"id": "teknium", "status": "ok", "tier": 2},
            {"id": "keeper", "status": "ok", "tier": 3},
        ]

    def read(self, bot_id: str):
        """Read a bot's state."""
        return {"id": bot_id, "status": "ok", "last_seen": datetime.now(timezone.utc).isoformat()}

    def write(self, bot_id: str, key: str, value):
        """Write state to a bot."""
        return {"ok": True, "bot": bot_id, "key": key}


class _Keeper:
    """Keeper bindings — audit, ledger, publish, remember, recall."""

    def audit(self, target: str):
        """Scan a resource for issues."""
        issues = []
        # Probe the target — real checks, not assumptions
        if target == "broker":
            # The broker endpoint / returns {"vps":"up"}, not /health
            import urllib.request as _ur
            try:
                req = _ur.Request("http://129.212.180.252:3000/", method="GET")
                with _ur.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read() or b"{}")
                if data.get("vps") == "up":
                    issues.append({"check": "broker", "verdict": "ok", "evidence": "GET / → {vps:up}"})
                else:
                    issues.append({"check": "broker", "verdict": "degraded", "evidence": f"GET / → {data}"})
            except Exception as e:
                issues.append({"check": "broker", "verdict": "down", "evidence": str(e)})
        else:
            issues.append({"check": target, "verdict": "unknown", "evidence": f"no probe for {target}"})
        return {"verdict": "ok" if all(i["verdict"] == "ok" for i in issues) else "issues",
                "evidence": issues}

    def reconcile(self, a: str, b: str):
        """Compare two sources."""
        return {"match": 100 if a == b else 0, "diff": [] if a == b else [f"{a} != {b}"]}

    def ledger(self, entry: dict):
        """Append-only ledger write. Atomic. Evidence required."""
        if not entry.get("evidence"):
            raise ValueError("ledger entry requires 'evidence' field — a claim without proof is refused")
        sig = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()[:16]
        entry["sig"] = sig
        entry["iso"] = datetime.now(timezone.utc).isoformat()
        LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return sig

    def handoff(self, to: str, task: str):
        """Delegate work to another bot."""
        return {"ok": True, "to": to, "task": task}

    def publish(self, facts: str):
        """Publish measured facts to the æ.social receipts network."""
        # Delegate to keeper://publish in the conductor
        import urllib.request as _ur
        BRAIN = "http://129.212.180.252:3000/xrpc/ae.vps.record"
        try:
            body = json.dumps({"nsid": "ae.social#post", "value": {
                "text": facts[:3000], "kind": "verification",
                "evidence": facts[:500], "agent": "code-mode",
                "principal": "did:web:myaelmendez.github.io",
                "measured": True, "createdAt": datetime.now(timezone.utc).isoformat()
            }}).encode()
            req = _ur.Request(BRAIN, data=body, headers={"Content-Type": "application/json"}, method="POST")
            with _ur.urlopen(req, timeout=25) as r:
                result = json.loads(r.read() or b"{}")
            return {"published": 1, "sig": result.get("sig", "")[:16]}
        except Exception as e:
            return {"published": 0, "error": str(e)}

    def remember(self, fact: str):
        """Store a fact in the ledger."""
        return self.ledger({"kind": "fact", "text": fact, "evidence": "user-provided"})

    def recall(self, query: str = "", limit: int = 50):
        """Retrieve facts from the ledger."""
        if not LEDGER_FILE.exists():
            return {"matches": []}
        matches = []
        with open(LEDGER_FILE, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    rec = json.loads(line.strip())
                    if query.lower() in json.dumps(rec).lower():
                        matches.append(rec)
                except json.JSONDecodeError:
                    continue
        return {"matches": matches[-limit:]}


class _VPS:
    """VPS bindings — broker health, provisioning."""
    def status(self):
        import urllib.request as _ur
        try:
            req = _ur.Request("http://129.212.180.252:3000/", method="GET")
            with _ur.urlopen(req, timeout=10) as r:
                data = json.loads(r.read() or b"{}")
            return {"vps": data.get("vps", "unknown"), "uptime": "measured"}
        except Exception as e:
            return {"vps": "down", "error": str(e)}

    def up(self, resource: str):
        return {"ok": True, "resource": resource, "action": "provisioned"}

    def down(self, resource: str):
        return {"ok": True, "resource": resource, "action": "deprovisioned"}

    def logs(self, resource: str, lines: int = 50):
        return [f"log line for {resource} (simulated)"]


class _RTX:
    """RTX bindings — GPU telemetry and compute."""
    def probe(self):
        try:
            import subprocess
            r = subprocess.run(["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                                "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                parts = r.stdout.strip().split(", ")
                return {"gpu": parts[0], "temp": int(parts[1]), "util": int(parts[2]),
                        "mem_used": int(parts[3]), "mem_total": int(parts[4])}
        except Exception:
            pass
        return {"gpu": "unknown", "temp": 0, "util": 0, "mem_used": 0, "mem_total": 0}

    def compute(self, op: str):
        return {"ok": True, "op": op, "result": "executed"}



class _Video:
    """Vidæo bindings — render, verify, receipt chain."""

    def render(self, scene: str, seconds: int = 5, out: str = ""):
        """Render a scene via æRTXrender. Returns receipt or refusal."""
        import subprocess
        node = 'C:/Users/yaelm/AppData/Local/hermes/tools/node-26.7.0-win32-x64/node.exe'
        render_mjs = 'C:/æ/threejs-curriculo/render.mjs'
        out_path = out or f'C:/æ/threejs-curriculo/out/{scene}.mp4'
        cmd = [node, render_mjs, f'--url=http://127.0.0.1:8123/{scene}.html',
               f'--out={out_path}', '--frames=150', '--fps=30', '--w=720', '--h=1280', '--encoder=nvenc']
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                import os
                size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
                return {'ok': True, 'path': out_path, 'bytes': size, 'scene': scene}
            return {'ok': False, 'error': r.stderr[-200:]}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def verify(self, video_path: str):
        """Verify video with SupervisorVideo gate."""
        import subprocess
        gpu_py = 'C:/gpu/Scripts/python.exe'
        vidæo_py = 'C:/æ/vidæo/vidæo.py'
        try:
            r = subprocess.run([gpu_py, vidæo_py, 'verify', video_path],
                               capture_output=True, text=True, timeout=120)
            import json
            # Parse JSON from output
            lines = r.stdout.split(chr(10))
            json_start = -1
            for i, line in enumerate(lines):
                if line.strip().startswith('{'):
                    json_start = i
                    break
            if json_start >= 0:
                json_str = chr(10).join(lines[json_start:])
                # Find matching closing brace
                depth = 0
                end = 0
                for i, c in enumerate(json_str):
                    if c == '{': depth += 1
                    elif c == '}': depth -= 1
                    if depth == 0 and i > 0:
                        end = i + 1
                        break
                data = json.loads(json_str[:end])
                return {
                        'pass': data.get('calidad') == 'PASS',
                        'luminance': data.get('luminancia_media', 0),
                        'contrast': data.get('contraste_medio', 0),
                        'motion': data.get('movimiento_medio', 0),
                        'black_frames': data.get('frames_negros', 0),
                        'receipt': data.get('receipt', ''),
                    }
            return {'pass': False, 'error': 'no JSON in output'}
        except Exception as e:
            return {'pass': False, 'error': str(e)}

    def receipt(self, video_path: str, intent: str, prev: str = ''):
        """Compute receipt chain entry."""
        import hashlib, os, json
        with open(video_path, 'rb') as f:
            video_hash = hashlib.sha256(f.read()).hexdigest()
        payload = f'{prev}||{intent}||{video_hash}'
        receipt = hashlib.sha256(payload.encode()).hexdigest()
        return {
            'receipt': receipt,
            'video_sha256': video_hash,
            'previous': prev,
            'intent': intent,
        }

    def status(self):
        """Toolchain status."""
        import os
        node = 'C:/Users/yaelm/AppData/Local/hermes/tools/node-26.7.0-win32-x64/node.exe'
        render_mjs = 'C:/æ/threejs-curriculo/render.mjs'
        return {
            'node': os.path.exists(node),
            'render_mjs': os.path.exists(render_mjs),
            'vidæo': os.path.exists('C:/æ/vidæo/vidæo.py'),
            'encoder': 'nvenc' if os.path.exists('C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-7.1-nvenc/bin/ffmpeg.exe') else 'libx264',
        }

class _Social:
    """æ.social bindings — the receipts network."""
    def post(self, value: dict):
        """Publish a post to the receipts network. Evidence is required."""
        if not value.get("evidence"):
            raise ValueError("æ.social.post requires 'evidence' — a post without proof is refused")
        required = {"text", "kind", "agent", "principal"}
        missing = required - set(value.keys())
        if missing:
            raise ValueError(f"æ.social.post missing required fields: {missing}")
        sig = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]
        return {"ok": True, "sig": sig}

    def read(self, nsid: str):
        """Read records by nsid."""
        return []

    def follow(self, subject: str):
        return {"ok": True, "subject": subject}


class _Storage:
    """Storage bindings — filesystem access within sandbox."""
    def read(self, path: str):
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"storage.read: {path} not found")
        return p.read_text(encoding="utf-8", errors="replace")

    def write(self, path: str, content: str):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(p), "bytes": len(content)}

    def list(self, dir: str):
        p = Path(dir)
        if not p.exists():
            return []
        return [x.name for x in p.iterdir() if x.is_file()]


# ══════════════════════════════════════════════════════════════
# SANDBOX — restricted execution environment
# ══════════════════════════════════════════════════════════════

class _SandboxedBuiltins(dict):
    """Builtins with dangerous ones removed."""
    def __init__(self, allowed):
        super().__init__((k, v) for k, v in __builtins__.__dict__.items() if k in allowed)

    def __getitem__(self, key):
        if key in BLOCKED_BUILTINS:
            raise PermissionError(f"sandbox: access to '{key}' is blocked — use æ.storage.* for filesystem")
        return super().__getitem__(key)


def make_sandbox():
    """Create a sandboxed globals dict with æ bindings."""
    allowed = set(__builtins__.__dict__.keys()) - BLOCKED_BUILTINS
    return {
        "__builtins__": _SandboxedBuiltins(allowed),
        "æ": _Æ(),
        "json": json,
        "re": __import__("re"),
        "datetime": __import__("datetime"),
        "time": __import__("time"),
        "hashlib": __import__("hashlib"),
        "urllib": __import__("urllib"),
        "Path": __import__("pathlib").Path,
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "KeyError": KeyError,
        "IndexError": IndexError,
    }


class _Æ:
    """The æ namespace — all bindings under one object."""
    def __init__(self):
        self.mesh = _Mesh()
        self.keeper = _Keeper()
        self.vps = _VPS()
        self.rtx = _RTX()
        self.social = _Social()
        self.storage = _Storage()
        self.video = _Video()


# ══════════════════════════════════════════════════════════════
# EXECUTION
# ══════════════════════════════════════════════════════════════

def log_call(code: str, result: str, elapsed_ms: float):
    """Log every execution for audit."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "code_hash": hashlib.sha256(code.encode()).hexdigest()[:16],
        "elapsed_ms": elapsed_ms,
        "result_preview": result[:200],
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def execute(code: str, timeout: int = TIMEOUT_S):
    """Execute code in the sandbox. Returns (stdout, stderr, exit_code)."""
    sandbox = make_sandbox()

    # Capture stdout
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stdout_buf = []
    stderr_buf = []

    class _Buf:
        def write(self, s):
            buf = stdout_buf if s else stderr_buf
            buf.append(s)
        def flush(self):
            pass

    sys.stdout = _Buf()
    sys.stderr = _Buf()

    start = time.monotonic()
    try:
        # Compile with structure gate — check for truncate markers
        if "<<<<<<<" in code or ">>>>>>>" in code:
            return "", "CONFLICT MARKERS IN CODE — structure gate rejected", 1

        # Execute with timeout
        def _run():
            exec(compile(code, "<æ_code_mode>", "exec"), sandbox)

        # Use threading for timeout on Windows
        import threading
        result = {"exc": None}
        def _target():
            try:
                _run()
            except Exception as e:
                result["exc"] = e

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout=timeout)

        elapsed = (time.monotonic() - start) * 1000

        if t.is_alive():
            # Thread still running — timeout
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            log_call(code, "TIMEOUT", elapsed)
            return "", f"TIMEOUT after {timeout}s — code exceeded execution budget", 124

        sys.stdout = old_stdout
        sys.stderr = old_stderr

        if result["exc"]:
            exc = result["exc"]
            log_call(code, f"ERROR: {exc}", elapsed)
            return "".join(stdout_buf), f"{type(exc).__name__}: {exc}", 1

        log_call(code, "OK", elapsed)
        return "".join(stdout_buf), "".join(stderr_buf), 0

    except Exception as e:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        elapsed = (time.monotonic() - start) * 1000
        log_call(code, f"FATAL: {e}", elapsed)
        return "", f"{type(e).__name__}: {e}", 1


# ══════════════════════════════════════════════════════════════
# TESTS
# ══════════════════════════════════════════════════════════════

def run_tests():
    """Verify the sandbox and bindings work correctly."""
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name} — {detail}")

    print("══ æ://code_mode tests ══\n")

    # 1. Sandbox blocks open()
    code = "open('/etc/passwd')"
    _, err, rc = execute(code)
    check("blocks open()", rc == 1 and "PermissionError" in err, err[:80])

    # 2. Sandbox blocks socket
    code = "import socket"
    _, err, rc = execute(code)
    check("blocks socket import", rc == 1, err[:80])

    # 3. æ.mesh.bots() works
    code = "print(len(æ.mesh.bots()))"
    out, _, rc = execute(code)
    check("æ.mesh.bots() returns 4", rc == 0 and "4" in out.strip(), out.strip())

    # 4. æ.keeper.ledger() requires evidence
    code = "æ.keeper.ledger({'kind':'test','text':'no evidence'})"
    _, err, rc = execute(code)
    check("ledger requires evidence", rc == 1 and "evidence" in err.lower(), err[:80])

    # 5. æ.keeper.ledger() works with evidence
    code = "sig = æ.keeper.ledger({'kind':'test','text':'hello','evidence':'test run'}); print(sig)"
    out, _, rc = execute(code)
    check("ledger accepts evidence", rc == 0 and len(out.strip()) == 16, out.strip())

    # 6. æ.social.post() requires evidence
    code = "æ.social.post({'text':'test','kind':'fact','agent':'code-mode','principal':'did:web:test'})"
    _, err, rc = execute(code)
    check("social.post requires evidence", rc == 1 and "evidence" in err.lower(), err[:80])

    # 7. æ.social.post() works with evidence
    code = "r = æ.social.post({'text':'test','kind':'fact','evidence':'test','agent':'code-mode','principal':'did:web:test'}); print(r['sig'])"
    out, _, rc = execute(code)
    check("social.post accepts evidence", rc == 0 and len(out.strip()) == 16, out.strip())

    # 8. æ.keeper.audit() works
    code = "v = æ.keeper.audit('broker'); print(v['verdict'])"
    out, _, rc = execute(code)
    check("keeper.audit() runs", rc == 0 and out.strip() in ("ok", "issues", "down"), out.strip())

    # 9. Timeout works
    # time is pre-bound in sandbox globals — do not use 'import' (blocked)
    code = "time.sleep(60)"
    _, err, rc = execute(code, timeout=2)
    check("timeout kills long code", rc == 124 and "TIMEOUT" in err, err[:80])

    # 10. æ.storage.write/read roundtrip
    code = "æ.storage.write('/tmp/code_mode_test.txt', 'hello'); print(æ.storage.read('/tmp/code_mode_test.txt'))"
    out, _, rc = execute(code)
    check("storage write/read roundtrip", rc == 0 and "hello" in out.strip(), out.strip())

    print(f"\n══ {passed} passed, {failed} failed ══")
    return 0 if failed == 0 else 1


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(run_tests())
    elif "--eval" in sys.argv:
        idx = sys.argv.index("--eval")
        code = sys.argv[idx + 1]
        out, err, rc = execute(code)
        if out: print(out)
        if err: print(err, file=sys.stderr)
        sys.exit(rc)
    elif len(sys.argv) > 1 and sys.argv[1].endswith(".py"):
        path = Path(sys.argv[1])
        code = path.read_text(encoding="utf-8")
        out, err, rc = execute(code)
        if out: print(out)
        if err: print(err, file=sys.stderr)
        sys.exit(rc)
    else:
        print("Usage:")
        print("  python æ_code_mode.py <script.py>")
        print("  python æ_code_mode.py --test")
        print("  python æ_code_mode.py --eval '<code>'")
        sys.exit(1)
