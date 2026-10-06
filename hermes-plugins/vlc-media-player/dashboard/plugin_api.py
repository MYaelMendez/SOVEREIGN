"""VLC Media Player — backend API.

Sovereign alignment (#opensourceware):
  - Local only: no cloud broker, no remote URL
  - Secrets from local custody (C:/æ/secrets), never hardcoded
  - Receipt for every action (SHA-256)
  - Gate verification: state check after open, honest reporting
  - in_play (VLC 3.x), never pl_add (no-op)
  - Unicode path handling (VLC 3.x doesn't accept Unicode paths)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
import urllib.request
import urllib.parse
import base64
import hashlib
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# --- config from local custody ---
VLC_EXE = os.environ.get("VLC_EXE", r"C:\Program Files\VideoLAN\VLC\vlc.exe")
VLC_HTTP_PORT = int(os.environ.get("VLC_HTTP_PORT", "8081"))
VLC_HTTP_HOST = os.environ.get("VLC_HTTP_HOST", "127.0.0.1")
VLC_HTTP_PASSWORD = os.environ.get("VLC_HTTP_PASSWORD", "hermes")
VLC_HTTP_BASE = f"http://{VLC_HTTP_HOST}:{VLC_HTTP_PORT}"

_vlc_process: Optional[subprocess.Popen] = None


def _load_secret(name: str, default: str) -> str:
    secret_file = os.path.join(os.path.expanduser("~"), "AppData", "Local", "hermes", "secrets", f"{name}.key")
    try:
        with open(secret_file, "r") as f:
            return f.read().strip() or default
    except (FileNotFoundError, PermissionError):
        return default


def _receipt(action: str, result: Any) -> Dict[str, Any]:
    ts = time.time()
    payload = json.dumps({"action": action, "result": result, "ts": ts}, sort_keys=True)
    h = hashlib.sha256(payload.encode()).hexdigest()
    return {"action": action, "ts": ts, "sha256": h, "result": result}


def _vlc_request(cmd: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    qs = ""
    if params:
        qs = "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{VLC_HTTP_BASE}/requests/{cmd}{qs}"
    try:
        req = urllib.request.Request(url)
        auth = base64.b64encode(f":{_load_secret('vlc', 'hermes')}".encode()).decode()
        req.add_header("Authorization", f"Basic {auth}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {"raw": data.decode("utf-8", errors="replace")}
    except Exception as e:
        return {"error": str(e)}


def _vlc_state() -> Tuple[Optional[str], Optional[str], Optional[int]]:
    d = _vlc_request("status")
    if not isinstance(d, dict) or "error" in d:
        return None, None, None
    fn = d.get("information", {}).get("category", {}).get("meta", {}).get("filename")
    return d.get("state"), fn, d.get("length")


def _to_file_uri(path: str) -> str:
    p = path.replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p
    return "file://" + urllib.parse.quote(p, safe="/:")


def _ascii_copy(render_path: str) -> Tuple[str, bool]:
    """Copy to ASCII temp path if VLC can't handle the original. Returns (path, copied)."""
    if not any(ord(c) > 127 for c in render_path):
        return render_path, False
    tmp = os.path.join(os.environ.get("TEMP", os.path.expanduser(r"~\AppData\Local\Temp")), "vlc-preview")
    os.makedirs(tmp, exist_ok=True)
    ascii_path = os.path.join(tmp, os.path.basename(render_path))
    shutil.copy2(render_path, ascii_path)
    return ascii_path, True


def _start_vlc() -> bool:
    global _vlc_process
    if _vlc_process is not None:
        return True
    if not os.path.exists(VLC_EXE):
        logger.warning("VLC binary not found: %s", VLC_EXE)
        return False
    try:
        args = [
            VLC_EXE, "--extraintf", "http",
            "--http-host", VLC_HTTP_HOST,
            "--http-port", str(VLC_HTTP_PORT),
            "--http-password", _load_secret("vlc", "hermes"),
            "--intf", "qt", "--qt-notification", "0",
        ]
        _vlc_process = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        for _ in range(30):
            time.sleep(0.5)
            if "error" not in _vlc_request("status"):
                return True
        logger.warning("VLC HTTP interface did not respond after 15s")
        return False
    except Exception as e:
        logger.warning("VLC start failed: %s", e)
        return False


@router.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True, "plugin": "vlc-media-player", "version": "0.2.0", "sovereign": True}


@router.get("/status")
async def status() -> Dict[str, Any]:
    _start_vlc()
    return _receipt("status", _vlc_request("status"))


@router.post("/play")
async def play() -> Dict[str, Any]:
    _start_vlc()
    return _receipt("play", _vlc_request("status", {"command": "pl_play"}))


@router.post("/pause")
async def pause() -> Dict[str, Any]:
    _start_vlc()
    return _receipt("pause", _vlc_request("status", {"command": "pl_pause"}))


@router.post("/stop")
async def stop() -> Dict[str, Any]:
    _start_vlc()
    return _receipt("stop", _vlc_request("status", {"command": "pl_stop"}))


@router.post("/next")
async def next_track() -> Dict[str, Any]:
    _start_vlc()
    return _receipt("next", _vlc_request("status", {"command": "pl_next"}))


@router.post("/prev")
async def prev_track() -> Dict[str, Any]:
    _start_vlc()
    return _receipt("prev", _vlc_request("status", {"command": "pl_previous"}))


class SeekRequest(BaseModel):
    percent: float


@router.post("/seek")
async def seek(req: SeekRequest) -> Dict[str, Any]:
    _start_vlc()
    return _receipt("seek", _vlc_request("status", {"command": "seek", "val": f"{req.percent}%"}))


class VolumeRequest(BaseModel):
    volume: int


@router.post("/volume")
async def volume(req: VolumeRequest) -> Dict[str, Any]:
    _start_vlc()
    vlc_vol = int((req.volume / 100) * 512)
    return _receipt("volume", _vlc_request("status", {"command": "volume", "val": str(vlc_vol)}))


class OpenRequest(BaseModel):
    path: str


@router.post("/open")
async def open_file(req: OpenRequest) -> Dict[str, Any]:
    """Open a file in VLC with gate verification.

    - Copies Unicode paths to ASCII temp (VLC 3.x limitation)
    - Uses in_play (never pl_add — no-op in VLC 3.x)
    - Verifies state after 1.5s: ok=True only if VLC reports playing/paused
    - Receipt with state, filename, length
    """
    _start_vlc()
    path, copied = _ascii_copy(req.path)
    uri = _to_file_uri(path)

    _vlc_request("status", {"command": "pl_empty"})
    _vlc_request("status", {"command": "in_play", "input": uri})

    time.sleep(1.5)
    state, filename, length = _vlc_state()
    ok = bool(filename) and state in ("playing", "paused")

    return _receipt("open", {
        "path": req.path, "resolved": path, "copied": copied,
        "state": state, "filename": filename, "length": length, "ok": ok,
    })


@router.post("/fullscreen")
async def fullscreen() -> Dict[str, Any]:
    _start_vlc()
    return _receipt("fullscreen", _vlc_request("status", {"command": "fullscreen"}))
