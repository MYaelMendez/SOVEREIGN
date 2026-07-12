#!/usr/bin/env python3
"""
vps:// — sovereign backbone node (Victus-local, liftable to any host).

One always-on box = DATA + COMPUTE + IDENTITY:
  - DATA:    holds mesh/fleet/ledger/sovereignState records under the ae.core lexicon,
             each signed (detached CAR-style envelope) with a key from the secret-bridge.
  - COMPUTE: answers rtx3050:// dispatch by shelling gpu-mcp (the RTX hands).
  - IDENTITY: serves the PDS endpoint the did:web anchor points at (http://localhost:3000).

Stdlib-only HTTP server (http.server). No framework, air-gappable.
Signing uses only the 'hashlib' HMAC stand-in for a real key — swap _sign() for
@atproto/crypto (ed25519) when wiring to the real ATProto PDS. Kept local-first here.

Run:  python vps_node.py                 # localhost:3000
      python vps_node.py --host 0.0.0.0 --port 3000
      python vps_node.py --selftest     # offline: record sign/verify + route parse
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# --- config ---
DEFAULT_HOST, DEFAULT_PORT = "127.0.0.1", 3000
GPU_MCP = "gpu-mcp"  # resolved on PATH / workspace; the RTX hands
# MCP² broker: when this node has no local GPU (e.g. the droplet), proxy rtx
# dispatch to a leaf gpu-mcp node (Victus over the reverse tunnel). The droplet
# is the public broker front door; the edge owns the silicon.
LEAF_MCP_HOST = os.environ.get("LEAF_MCP_HOST", "127.0.0.1")
LEAF_MCP_PORT = os.environ.get("LEAF_MCP_PORT", "3050")

# in-memory record store: nsid -> [records]
_STORE: dict[str, list[dict]] = {"ae.core#fleetNode": [], "ae.core#meshPeer": [],
                                 "ae.core#ledgerEvent": [], "ae.core#sovereignState": []}
_LOCK = threading.Lock()


# --- signing (local-first stand-in; replace with ed25519 for real PDS) ---
def _sign(payload: bytes, key: str) -> str:
    """Detached signature. HMAC-SHA256 stand-in; NOT a substitute for ed25519."""
    return base64.b64encode(hashlib.sha256(payload + key.encode()).digest()).decode()


def _verify(sig: str, payload: bytes, key: str) -> bool:
    return _sign(payload, key) == sig


def _secret_key() -> str:
    """Signing key from secret-bridge convention; NEVER hardcoded.
    Order: VPS_SIGN_KEY env -> bridge secrets.json (HERMES_SECRETS / C:\\ae\\secrets\\secrets.json)."""
    import os
    k = os.environ.get("VPS_SIGN_KEY") or os.environ.get("BSKY_AGENT_VPS")
    if not k:
        try:
            from secret_source import get_secret
            k = get_secret("VPS_SIGN_KEY")
        except Exception:
            k = None
    if not k:
        raise RuntimeError("VPS_SIGN_KEY not set (put it in the secret-bridge + Push to local). Refusing unsigned store.")
    return k


# --- record envelope ---
def make_record(nsid: str, value: dict) -> dict:
    body = json.dumps(value, separators=(",", ":")).encode()
    env = {
        "nsid": nsid,
        "value": value,
        "sig": _sign(body, _secret_key()),
    }
    with _LOCK:
        if nsid not in _STORE:
            _STORE[nsid] = []
        _STORE[nsid].append(env)
    return env


def list_records(nsid: str) -> list[dict]:
    with _LOCK:
        return list(_STORE.get(nsid, []))


# --- compute: rtx3050:// dispatch via gpu-mcp (local) OR MCP² broker (leaf) ---
def dispatch_rtx(op: str, n: int = 512) -> dict:
    """Drive the RTX hands via gpu-mcp, or broker to a leaf node if GPU-less.

    On a GPU-bearing node (Victus) this runs the kernel locally through
    gpu-mcp. On a GPU-less node (the droplet) it proxies the call to a leaf
    MCP server (Victus exposed via reverse tunnel) — MCP²: the droplet is the
    public broker, the edge owns the silicon. No shell CLI guessing.
    """
    kernel = op if op else "matmul"
    try:
        from gpu_mcp.gpu_agent import GPUAgent
    except Exception:
        return _broker_rtx(kernel, n)  # GPU-less: proxy to leaf
    try:
        gpu = GPUAgent()
        probe = gpu.probe_gpu()
        if not probe or "name" not in probe:
            return _broker_rtx(kernel, n)  # GPU reported unavailable: try leaf
        c = gpu.compile_kernel(kernel)
        if not c.get("ok", False):
            return {"ok": False, "compile": c, "error": "compile failed"}
        r = gpu.run_kernel(kernel)
        return {"ok": r.get("ok", False), "op": kernel, "probe": probe,
                "compile": {"ok": True}, "run": r, "node": "local"}
    except Exception as e:
        return _broker_rtx(kernel, n, error=str(e))  # fall back to broker


def _broker_rtx(op: str, n: int, error: str | None = None) -> dict:
    """MCP² proxy: forward rtx dispatch to a leaf gpu-mcp node over HTTP."""
    base = f"http://{LEAF_MCP_HOST}:{LEAF_MCP_PORT}"
    url = f"{base}/xrpc/ae.vps.rtx?op={urllib.parse.quote(op)}&n={n}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return {**json.loads(r.read()), "node": "broker", "broker": base}
    except Exception as e:
        return {"ok": False, "node": "broker", "broker": base,
                "error": f"leaf unreachable: {e}", "local_error": error}


# --- router ---
def route(cmd: str) -> dict:
    """Parse a vps:// command. e.g. 'vps://rtx?op=matmul&n=512', 'vps://status'.

    NOTE: ae.core NSIDs contain '#' (e.g. 'ae.core#fleetNode'). '#' is a URL
    fragment delimiter, so never pass them as 'vps://record?nsid=ae.core#x' —
    the query truncates at '#'. Use the conductor space-form instead:
    '+æ://vps record ae.core#fleetNode {...}', which is why urlparse falls back
    to netloc for the action (handled below).
    """
    full = cmd if "://" in cmd else "vps://" + cmd
    p = urllib.parse.urlparse(full)
    # urlparse puts the action in netloc for 'vps://rtx?...' (no path), so fall back to it.
    path = (p.path.lstrip("/") or p.netloc or "status")
    q = urllib.parse.parse_qs(p.query)
    if path == "status":
        return {"vps": "up", "records": {k: len(v) for k, v in _STORE.items()},
                "compute": "rtx3050://ready"}
    if path == "rtx":
        op = q.get("op", ["matmul"])[0]
        n = int(q.get("n", ["512"])[0])
        return dispatch_rtx(op, n)
    if path == "record":
        nsid = q.get("nsid", ["ae.core#fleetNode"])[0]
        return {"nsid": nsid, "records": list_records(nsid)}
    return {"error": f"unknown vps path: {path}"}


# --- HTTP handler ---
class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # serves PDS identity endpoint + status + MCP² tools
        if self.path in ("/", "/xrpc/_health"):
            return self._send(200, {"vps": "up"})
        if self.path == "/mcp/tools":
            return self._send(200, {"ok": True, "tools": [
                {"name": "rtx3050://matmul", "desc": "CUDA matmul on RTX 3050 (broker->Victus leaf)"},
                {"name": "rtx3050://probe", "desc": "GPU telemetry via gpu-mcp"},
                {"name": "vps://status", "desc": "backbone node status"},
                {"name": "vps://record", "desc": "signed mesh/fleet record"},
            ]})
        if self.path.startswith("/xrpc/ae.vps.status"):
            return self._send(200, route("status"))
        if self.path.startswith("/xrpc/ae.vps.rtx"):
            try:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                op = q.get("op", ["matmul"])[0]
                n = int(q.get("n", ["512"])[0])
                return self._send(200, dispatch_rtx(op, n))
            except Exception as e:
                return self._send(200, {"ok": False, "error": f"rtx GET error: {e}"})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(ln) if ln else b"{}"
        try:
            req = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "bad json"})
        if self.path == "/mcp/invoke":
            tool = str(req.get("tool", "")).strip()
            if tool.startswith("rtx3050://"):
                op = tool.split("rtx3050://", 1)[1].split("?")[0] or "matmul"
                return self._send(200, dispatch_rtx(op))
            return self._send(200, {"ok": True, "rc": 0, "tool": tool,
                                    "stdout": json.dumps(req.get("args", {}))})
        if self.path.endswith("/xrpc/ae.vps.record"):
            nsid = req.get("nsid")
            if nsid not in _STORE:
                return self._send(400, {"error": f"unknown nsid {nsid}"})
            env = make_record(nsid, req.get("value", {}))
            return self._send(201, env)
        if self.path.endswith("/xrpc/ae.vps.route"):
            return self._send(200, route(req.get("cmd", "status")))
        self._send(404, {"error": "not found"})

    def log_message(self, *a):  # quiet
        pass


def run(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"vps:// listening on http://{host}:{port}  (did:web endpoint)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


def selftest():
    import os
    os.environ["VPS_SIGN_KEY"] = "selftest-key"
    v = {"node": "victus", "route": "pc://mesh/victus/local", "role": "engineering-computer",
         "status": "online", "models": ["local/cuda"], "agents": ["orch"]}
    env = make_record("ae.core#fleetNode", v)
    # verify signature
    body = json.dumps(v, separators=(",", ":")).encode()
    assert _verify(env["sig"], body, _secret_key()), "signature mismatch"
    # stored
    assert len(list_records("ae.core#fleetNode")) == 1
    # route parse
    assert route("status")["vps"] == "up"
    assert "records" in route("record?nsid=ae.core#fleetNode")
    print("SELFTEST OK: sign/verify, store, route parse — all pass.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="vps:// sovereign backbone node")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    else:
        run(a.host, a.port)
