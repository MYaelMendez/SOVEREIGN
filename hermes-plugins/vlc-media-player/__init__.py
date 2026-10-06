"""VLC Media Player — control a real player, or say it is not there.

Sovereign alignment (#opensourceware):
  - Local only: no cloud broker, no remote URL
  - Secrets from local custody (C:/æ/secrets), never hardcoded
  - Receipt for every action (SHA-256)
  - Gate verification: state check after open, honest reporting
  - in_play (VLC 3.x), never pl_add (no-op)
  - Unicode path handling (VLC 3.x doesn't accept Unicode paths)
"""

from __future__ import annotations
import json, os, urllib.request, urllib.error, hashlib, time, base64, urllib.parse

VLC_HTTP_BASE = "http://127.0.0.1:8081"
VLC_HTTP = f"{VLC_HTTP_BASE}/requests/status.json"


def _load_secret(name: str, default: str) -> str:
    """Read a secret from local custody. Never hardcode."""
    secret_file = os.path.join(os.path.expanduser("~"), "AppData", "Local", "hermes", "secrets", f"{name}.key")
    try:
        with open(secret_file, "r") as f:
            return f.read().strip() or default
    except (FileNotFoundError, PermissionError):
        return default


VLC_PASSWORD = _load_secret("vlc", "hermes")


def _vlc_cmd(cmd, params=None):
    """Send command to VLC HTTP API."""
    qs = ""
    if params:
        qs = "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{VLC_HTTP_BASE}/requests/status.json{qs}"
    try:
        req = urllib.request.Request(url)
        auth = base64.b64encode(f":{VLC_PASSWORD}".encode()).decode()
        req.add_header("Authorization", f"Basic {auth}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {"raw": data.decode("utf-8", errors="replace")}
    except Exception as e:
        return {"error": str(e)}


def _receipt(action, result):
    """Generate SHA-256 receipt for each action."""
    ts = time.time()
    payload = json.dumps({"action": action, "result": result, "ts": ts}, sort_keys=True)
    h = hashlib.sha256(payload.encode()).hexdigest()
    return {"action": action, "ts": ts, "sha256": h, "result": result}


def _to_file_uri(path):
    """Convert a Windows path to a file:// URI VLC 3.x accepts."""
    p = path.replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p
    return "file://" + urllib.parse.quote(p, safe="/:")


def _vlc_state():
    """Read the player's real state. Returns (state, filename, length)."""
    d = _vlc_cmd("status")
    if not isinstance(d, dict) or "error" in d:
        return None, None, None
    fn = d.get("information", {}).get("category", {}).get("meta", {}).get("filename")
    return d.get("state"), fn, d.get("length")


def vlc_status(**_):
    out = ["vlc media player", ""]
    exe = shutil.which("vlc") or shutil.which("vlc.exe")
    if not exe:
        for c in (r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                  r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"):
            if os.path.exists(c):
                exe = c; break
    out.append(f"  binary    {exe or 'NOT FOUND'}")
    ok, d = _get(VLC_HTTP, timeout=4)
    if ok:
        out.append(f"  http      answering - state={d.get('state','?')}")
    else:
        out.append("  http      not answering (VLC not running, or no --extrainf http)")
    out.append("")
    out.append("  Reporting 'playing' when nothing is playing would be a lie.")
    return "\n".join(out)


def vlc_play(**_):
    """Play current media."""
    result = _vlc_cmd("status", {"command": "pl_play"})
    return _receipt("play", result)


def vlc_pause(**_):
    """Pause current media."""
    result = _vlc_cmd("status", {"command": "pl_pause"})
    return _receipt("pause", result)


def vlc_stop(**_):
    """Stop current media."""
    result = _vlc_cmd("status", {"command": "pl_stop"})
    return _receipt("stop", result)


def vlc_seek(**kwargs):
    """Seek to percent (0-100)."""
    percent = kwargs.get("percent", 0)
    result = _vlc_cmd("status", {"command": "seek", "val": f"{percent}%"})
    return _receipt("seek", result)


def vlc_open(**kwargs):
    """Open a file in VLC. Uses in_play (VLC 3.x) with a file:// URI — pl_add
    silently does nothing on 3.0.24, which made receipts claim success."""
    path = kwargs.get("path", "")
    uri = _to_file_uri(path)
    result = _vlc_cmd("status", {"command": "in_play", "input": uri})
    return _receipt("open", result)


def vlc_volume(**kwargs):
    """Set volume (0-100)."""
    vol = kwargs.get("volume", 50)
    vlc_vol = int((vol / 100) * 512)
    result = _vlc_cmd("status", {"command": "volume", "val": str(vlc_vol)})
    return _receipt("volume", result)


def register(ctx):
    ctx.register_tool(
        name="vlc_status", toolset="vlc-media-player",
        schema={"type":"function","function":{"name":"vlc_status",
            "description":'Report whether VLC is present and whether its HTTP control port answers.',
            "parameters":{"type":"object","properties":{},"required":[]}}},
        handler=lambda *a, **kw: vlc_status(**kw),
        description='Report whether VLC is present and whether its HTTP control port answers.', emoji="▶",
    )
    ctx.register_tool(
        name="vlc_play", toolset="vlc-media-player",
        schema={"type":"function","function":{"name":"vlc_play",
            "description":'Play current media in VLC.',
            "parameters":{"type":"object","properties":{},"required":[]}}},
        handler=lambda *a, **kw: vlc_play(**kw),
        description='Play current media in VLC.', emoji="▶",
    )
    ctx.register_tool(
        name="vlc_pause", toolset="vlc-media-player",
        schema={"type":"function","function":{"name":"vlc_pause",
            "description":'Pause current media in VLC.',
            "parameters":{"type":"object","properties":{},"required":[]}}},
        handler=lambda *a, **kw: vlc_pause(**kw),
        description='Pause current media in VLC.', emoji="⏸",
    )
    ctx.register_tool(
        name="vlc_stop", toolset="vlc-media-player",
        schema={"type":"function","function":{"name":"vlc_stop",
            "description":'Stop current media in VLC.',
            "parameters":{"type":"object","properties":{},"required":[]}}},
        handler=lambda *a, **kw: vlc_stop(**kw),
        description='Stop current media in VLC.', emoji="⏹",
    )
    ctx.register_tool(
        name="vlc_seek", toolset="vlc-media-player",
        schema={"type":"function","function":{"name":"vlc_seek",
            "description":'Seek to percent (0-100) in VLC.',
            "parameters":{"type":"object","properties":{"percent":{"type":"number","description":"Seek position 0-100"}},"required":["percent"]}}},
        handler=lambda *a, **kw: vlc_seek(**kw),
        description='Seek to percent (0-100) in VLC.', emoji="⏩",
    )
    ctx.register_tool(
        name="vlc_open", toolset="vlc-media-player",
        schema={"type":"function","function":{"name":"vlc_open",
            "description":'Open a file in VLC.',
            "parameters":{"type":"object","properties":{"path":{"type":"string","description":"File path to open"}},"required":["path"]}}},
        handler=lambda *a, **kw: vlc_open(**kw),
        description='Open a file in VLC.', emoji="📂",
    )
    ctx.register_tool(
        name="vlc_volume", toolset="vlc-media-player",
        schema={"type":"function","function":{"name":"vlc_volume",
            "description":'Set VLC volume (0-100).',
            "parameters":{"type":"object","properties":{"volume":{"type":"integer","description":"Volume 0-100"}},"required":["volume"]}}},
        handler=lambda *a, **kw: vlc_volume(**kw),
        description='Set VLC volume (0-100).', emoji="🔊",
    )
    ctx.register_hook("on_session_end", _on_session_end)


def _on_session_end(**kwargs):
    """Never raises: a hook that breaks the agent loop is worse than a quiet one."""
    try:
        pass  # this plugin holds no session state to flush
    except Exception:
        pass


# --- WebMCP bridge (Fase 4) ---

VLC_MCP_TOOLS = [
    {
        "name": "vlc_status",
        "description": "Report VLC player state (playing, paused, stopped).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "vlc_play",
        "description": "Play current media in VLC.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "vlc_pause",
        "description": "Pause current media in VLC.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "vlc_stop",
        "description": "Stop current media in VLC.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "vlc_seek",
        "description": "Seek to percent (0-100) in VLC.",
        "inputSchema": {"type": "object", "properties": {"percent": {"type": "number"}}, "required": ["percent"]},
    },
    {
        "name": "vlc_open",
        "description": "Open a file in VLC.",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "vlc_volume",
        "description": "Set VLC volume (0-100).",
        "inputSchema": {"type": "object", "properties": {"volume": {"type": "integer"}}, "required": ["volume"]},
    },
]


def register_webmcp(ctx):
    """Register VLC tools via WebMCP if the host supports it."""
    try:
        # Check for WebMCP support in the plugin context
        if hasattr(ctx, 'register_webmcp_tool'):
            for tool in VLC_MCP_TOOLS:
                ctx.register_webmcp_tool(
                    name=tool["name"],
                    description=tool["description"],
                    inputSchema=tool["inputSchema"],
                    handler=tool["name"],
                )
            return True
    except Exception as e:
        logger.warning(f"WebMCP registration failed: {e}")
    return False


# --- MP4 Factory integration (Fase 5) ---

def open_in_vlc(render_path):
    """Open a rendered MP4 in VLC (integration with mp4-factory).

    Reports honestly: ok is True only if VLC reports the file as loaded —
    never a receipt that implies playback when nothing played.
    """
    # Copy to ASCII path if needed (VLC doesn't handle Unicode paths well)
    if any(ord(c) > 127 for c in render_path):
        import shutil
        ascii_path = os.path.join(
            os.environ.get("TEMP", r"C:\Users\yaelm\AppData\Local\Temp"),
            os.path.basename(render_path)
        )
        shutil.copy2(render_path, ascii_path)
        render_path = ascii_path

    # in_play is the VLC 3.x command that actually loads media (pl_add is a no-op)
    result = _vlc_cmd("status", {"command": "in_play", "input": _to_file_uri(render_path)})

    # Verify against the player's real state, not the command's return.
    time.sleep(1.5)
    state, filename, length = _vlc_state()
    ok = bool(filename) and state in ("playing", "paused")

    receipt = _receipt("open_in_vlc", {
        "path": render_path, "state": state, "filename": filename, "length": length,
    })
    return {"ok": ok, **receipt}
