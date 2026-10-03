#!/usr/bin/env python3
"""æ://rtx-leaf — the Victus GPU hands, served over HTTP for the MCP² broker.

The droplet (broker, GPU-less) proxies `rtx3050://` dispatches here through a
reverse SSH tunnel. This process is the LEAF: it owns the silicon.

Contract (must match vps_node._broker_rtx):
    GET /xrpc/ae.vps.rtx?op=<op>&n=<n>   -> JSON
    GET /health                          -> {"ok": true, ...}

Stdlib-only. No framework. Air-gappable.

Run:  python rtx_leaf.py                 # 127.0.0.1:3050
      python rtx_leaf.py --port 3050
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_HOST = os.environ.get("RTX_LEAF_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("RTX_LEAF_PORT", "3050"))

# ops this leaf can answer without a CUDA build present
_NVIDIA_SMI = [
    "nvidia-smi",
    "--query-gpu=name,memory.total,memory.used,memory.free,"
    "utilization.gpu,temperature.gpu,driver_version,compute_cap",
    "--format=csv,noheader,nounits",
]


def _smi() -> dict:
    """Real GPU telemetry via nvidia-smi. Never invents a value."""
    try:
        r = subprocess.run(_NVIDIA_SMI, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return {"ok": False, "error": (r.stderr or "nvidia-smi failed").strip()[:200]}
        parts = [p.strip() for p in (r.stdout or "").strip().split(",")]
        if len(parts) < 8:
            return {"ok": False, "error": "unexpected nvidia-smi shape", "raw": parts}
        return {
            "ok": True,
            "name": parts[0],
            "memory.total": int(parts[1]),
            "memory.used": int(parts[2]),
            "memory.free": int(parts[3]),
            "utilization.gpu": int(parts[4]),
            "temperature.gpu": int(parts[5]),
            "driver_version": parts[6],
            "compute_cap": parts[7],
            "memory.unit": "MiB",
        }
    except FileNotFoundError:
        return {"ok": False, "error": "nvidia-smi not found on PATH"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _nvcc() -> dict:
    try:
        r = subprocess.run(["nvcc", "--version"], capture_output=True, text=True, timeout=15)
        line = [l for l in (r.stdout or "").splitlines() if "release" in l.lower()]
        return {"ok": r.returncode == 0, "nvcc": line[0].strip() if line else None}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def dispatch(op: str, n: int) -> dict:
    """Answer one rtx3050:// op."""
    op = (op or "probe").strip().lower()
    t0 = time.time()

    if op in ("probe", "telemetry", "status"):
        smi = _smi()
        return {
            "ok": smi.get("ok", False),
            "op": "probe",
            "leaf": "victus",
            "probe": smi,
            "host_ms": round((time.time() - t0) * 1000, 2),
        }

    if op in ("matmul", "compute"):
        # Real CUDA path: delegate to gpu_mcp's GPUAgent if importable.
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from gpu_mcp.gpu_agent import GPUAgent  # type: ignore
            gpu = GPUAgent()
            probe = gpu.probe_gpu()
            if probe and "name" in probe:
                c = gpu.compile_kernel("matmul")
                if not c.get("ok", False):
                    return {"ok": False, "op": op, "error": "compile failed", "compile": c,
                            "leaf": "victus", "host_ms": round((time.time() - t0) * 1000, 2)}
                r = gpu.run_kernel("matmul")
                return {"ok": r.get("ok", False), "op": op, "n": n, "probe": probe,
                        "run": r, "leaf": "victus",
                        "host_ms": round((time.time() - t0) * 1000, 2)}
            return {"ok": False, "op": op, "leaf": "victus",
                    "error": "GPUAgent reported no GPU", "probe": probe,
                    "host_ms": round((time.time() - t0) * 1000, 2)}
        except Exception as e:
            smi = _smi()
            return {
                "ok": False,
                "op": op,
                "leaf": "victus",
                "error": f"cuda path unavailable: {type(e).__name__}: {e}",
                "probe": smi,
                "nvcc": _nvcc(),
                "host_ms": round((time.time() - t0) * 1000, 2),
            }

    if op == "nvcc":
        return {"ok": True, "op": "nvcc", "nvcc": _nvcc(), "leaf": "victus",
                "host_ms": round((time.time() - t0) * 1000, 2)}

    return {"ok": False, "op": op, "leaf": "victus",
            "error": f"unknown op: {op}", "known": ["probe", "matmul", "nvcc"],
            "host_ms": round((time.time() - t0) * 1000, 2)}


class Handler(BaseHTTPRequestHandler):
    server_version = "ae-rtx-leaf/1.0"

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)

        if u.path in ("/health", "/"):
            self._send(200, {"ok": True, "leaf": "victus", "service": "ae-rtx-leaf",
                             "port": self.server.server_address[1]})
            return

        if u.path == "/xrpc/ae.vps.rtx":
            op = (q.get("op", ["probe"])[0] or "probe")
            try:
                n = int(q.get("n", ["512"])[0])
            except ValueError:
                n = 512
            self._send(200, dispatch(op, n))
            return

        self._send(404, {"ok": False, "error": "not found", "path": u.path})

    def log_message(self, fmt, *args):
        print(f"[leaf] {self.address_string()} {fmt % args}", flush=True)


def run(host: str, port: int):
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"æ://rtx-leaf listening on http://{host}:{port}", flush=True)
    print(f"  GET /xrpc/ae.vps.rtx?op=probe|matmul|nvcc&n=512", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[leaf] stopped", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    a = ap.parse_args()
    run(a.host, a.port)
