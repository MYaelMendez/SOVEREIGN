#!/usr/bin/env bash
# æ://rtx-bridge — keep the Victus RTX hands reachable from the droplet broker.
#
# Tier 3 of the glocal mesh. Two long-lived processes, both self-healing:
#   1. the leaf      — serves /xrpc/ae.vps.rtx on 127.0.0.1:3050 (real GPU)
#   2. the tunnel    — reverse SSH  droplet:3050 -> Victus:3050
#
# WHY THE LEAF IS rtx_leaf.py AND NOT vps_node.py
#   glocal-mesh's contract sketch runs `vps_node.py` as the leaf. That does not
#   work on a machine without the gpu_mcp package: dispatch_rtx() catches the
#   ImportError and falls through to _broker_rtx(), which posts to
#   127.0.0.1:3050 — i.e. back into itself. Infinite loop. rtx_leaf.py serves
#   the /xrpc/ae.vps.rtx route directly and never calls dispatch_rtx, so there
#   is nothing to loop.
#
# Usage:
#   rtx-bridge.sh up        run both loops in the foreground (systemd/Startup entry)
#   rtx-bridge.sh start     detached start
#   rtx-bridge.sh stop      kill both
#   rtx-bridge.sh status    probe leaf + tunnel + the public broker path
#   rtx-bridge.sh logs      tail the logs
#   rtx-bridge.sh install   write the systemd --user unit (Linux/WSL)
#   rtx-bridge.sh startup   write the Windows Startup .vbs (Victus)

set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# MSYS path trap (documented in glocal-mesh + github-pages-deploy): this shell
# hands `python` an MSYS path (/c/æ/...), and the native Windows python.exe
# resolves it to C:\c\æ\... — a directory that does not exist. Convert to a
# native path for anything a native binary has to open. Python and ssh both
# need the converted form.
_native() {
  if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi
}

LEAF="$(_native "$DIR/rtx_leaf.py")"
LEAF_DIR="$(_native "$DIR")"
LOG_DIR="${RTX_BRIDGE_LOG_DIR:-$HOME/.hermes/logs}"
LEAF_LOG="$LOG_DIR/rtx_leaf.log"
TUN_LOG="$LOG_DIR/rtx_tunnel.log"

DROPLET_HOST="${DROPLET_HOST:-129.212.180.252}"
LEAF_PORT="${RTX_LEAF_PORT:-3050}"
REMOTE_PORT="${RTX_REMOTE_PORT:-$LEAF_PORT}"

mkdir -p "$LOG_DIR"

# --- process discovery (Windows: python.exe / ssh.exe ; POSIX: python3 / ssh) ---
# NOTE: `tasklist` does NOT expose command lines, so grepping it for "rtx_leaf"
# never matches. Use PowerShell CIM (wmic is removed on Win11 26200+).
_leaf_pids() {
  if command -v powershell >/dev/null 2>&1; then
    powershell -NoProfile -Command \
      "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { \$_.CommandLine -like '*rtx_leaf*' } | Select-Object -ExpandProperty ProcessId" \
      2>/dev/null | tr -d '\r' | grep -E '^[0-9]+$'
  else
    pgrep -f "rtx_leaf.py" 2>/dev/null
  fi
}

_tunnel_pids() {
  if command -v powershell >/dev/null 2>&1; then
    powershell -NoProfile -Command \
      "Get-CimInstance Win32_Process -Filter \"name='ssh.exe'\" | Where-Object { \$_.CommandLine -like '*-R*$REMOTE_PORT:127.0.0.1:$LEAF_PORT*' } | Select-Object -ExpandProperty ProcessId" \
      2>/dev/null | tr -d '\r' | grep -E '^[0-9]+$'
  else
    pgrep -f "ssh .*-R $REMOTE_PORT:127.0.0.1:$LEAF_PORT" 2>/dev/null
  fi
}

# The supervisor loops themselves. Killing only the python child leaves the
# `while true` alive, and it respawns the child 2s later — so `stop` must take
# the loops down too, not just their children.
_loop_pids() {
  if command -v powershell >/dev/null 2>&1; then
    powershell -NoProfile -Command       "Get-CimInstance Win32_Process -Filter \"name='bash.exe'\" | Where-Object { \$_.CommandLine -like '*rtx-bridge*' -and \$_.CommandLine -like '* up*' } | Select-Object -ExpandProperty ProcessId"       2>/dev/null | tr -d '
' | grep -E '^[0-9]+$'
  else
    pgrep -f "rtx-bridge.sh up" 2>/dev/null
  fi
}

_port_busy() {
  if command -v netstat >/dev/null 2>&1; then
    netstat -ano 2>/dev/null | grep -E "LISTENING" | grep -q ":$LEAF_PORT "
  else
    ss -tln 2>/dev/null | grep -q ":$LEAF_PORT "
  fi
}

# --- the two loops -----------------------------------------------------------
run_leaf() {
  while true; do
    echo "[$(date -u +%FT%TZ)] leaf starting on 127.0.0.1:$LEAF_PORT" >> "$LEAF_LOG"
    python "$LEAF" --host 127.0.0.1 --port "$LEAF_PORT" >> "$LEAF_LOG" 2>&1
    echo "[$(date -u +%FT%TZ)] leaf exited (rc=$?); restart in 2s" >> "$LEAF_LOG"
    sleep 2
  done
}

run_tunnel() {
  while true; do
    echo "[$(date -u +%FT%TZ)] tunnel up -> $DROPLET_HOST:$REMOTE_PORT" >> "$TUN_LOG"
    ssh -N -T \
      -o BatchMode=yes \
      -o ExitOnForwardFailure=yes \
      -o ServerAliveInterval=30 \
      -o ServerAliveCountMax=3 \
      -R "$REMOTE_PORT:127.0.0.1:$LEAF_PORT" \
      "root@$DROPLET_HOST" >> "$TUN_LOG" 2>&1
    echo "[$(date -u +%FT%TZ)] tunnel dropped (rc=$?); reconnect in 5s" >> "$TUN_LOG"
    sleep 5
  done
}

# --- verbs -------------------------------------------------------------------
cmd_up() {
  echo "æ://rtx-bridge up · leaf :$LEAF_PORT · tunnel -> $DROPLET_HOST:$REMOTE_PORT"
  echo "  logs: $LOG_DIR"
  run_leaf &   LEAF_JOB=$!
  run_tunnel & TUN_JOB=$!
  trap 'kill $LEAF_JOB $TUN_JOB 2>/dev/null; exit 0' INT TERM
  wait
}

cmd_start() {
  if _port_busy; then
    echo "leaf already listening on :$LEAF_PORT — stop first"
  else
    ( run_leaf ) &
    echo "leaf loop started (pid $!)"
  fi
  ( run_tunnel ) &
  echo "tunnel loop started (pid $!)"
  echo "note: detached loops do not survive a reboot; use 'install' or 'startup'"
}

cmd_stop() {
  # loops first, else they respawn the children we are about to kill
  loops="$(_loop_pids)"
  if [ -n "$loops" ]; then
    echo "$loops" | while read -r p; do [ -n "$p" ] && powershell -NoProfile -Command "Stop-Process -Id $p -Force" 2>/dev/null; done
    echo "loops stopped (pids: $(echo $loops | tr '
' ' '))"
  else
    echo "no loops running"
  fi

  lp="$(_leaf_pids)"
  if [ -n "$lp" ]; then
    echo "$lp" | while read -r p; do [ -n "$p" ] && powershell -NoProfile -Command "Stop-Process -Id $p -Force" 2>/dev/null; done
    echo "leaf stopped (pids: $(echo $lp | tr '\n' ' '))"
  else
    echo "leaf not running"
  fi

  tp="$(_tunnel_pids)"
  if [ -n "$tp" ]; then
    echo "$tp" | while read -r p; do [ -n "$p" ] && powershell -NoProfile -Command "Stop-Process -Id $p -Force" 2>/dev/null; done
    echo "tunnel stopped (pids: $(echo $tp | tr '\n' ' '))"
  else
    echo "tunnel not running"
  fi
}

cmd_status() {
  echo "── local leaf ──"
  if curl -s --max-time 6 "http://127.0.0.1:$LEAF_PORT/health"; then echo; else echo "  UNREACHABLE"; fi
  echo "── tunnel (droplet loopback) ──"
  ssh -o BatchMode=yes -o ConnectTimeout=8 "root@$DROPLET_HOST" \
      "curl -s --max-time 6 http://127.0.0.1:$REMOTE_PORT/health" 2>/dev/null \
    && echo || echo "  UNREACHABLE"
  echo "── public broker path ──"
  curl -s --max-time 20 "http://$DROPLET_HOST:3000/xrpc/ae.vps.rtx?op=probe" 2>/dev/null | head -c 400
  echo
}

cmd_logs() {
  echo "=== leaf ==="; tail -n 20 "$LEAF_LOG" 2>/dev/null || echo "(none)"
  echo "=== tunnel ==="; tail -n 20 "$TUN_LOG" 2>/dev/null || echo "(none)"
}

cmd_install() {
  UNIT_DIR="$HOME/.config/systemd/user"
  mkdir -p "$UNIT_DIR"
  cat > "$UNIT_DIR/glocal-rtx.service" <<EOF
[Unit]
Description=æ://rtx-bridge — Victus RTX hands for the glocal mesh
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/env bash $DIR/rtx-bridge.sh up
Restart=always
RestartSec=5
Environment=RTX_LEAF_PORT=$LEAF_PORT
Environment=RTX_REMOTE_PORT=$REMOTE_PORT
Environment=DROPLET_HOST=$DROPLET_HOST

[Install]
WantedBy=default.target
EOF
  echo "wrote $UNIT_DIR/glocal-rtx.service"
  echo "  systemctl --user daemon-reload"
  echo "  systemctl --user enable --now glocal-rtx"
  echo "  (survive logout: loginctl enable-linger \$USER)"
}

cmd_startup() {
  # Windows: a .vbs in Startup launches the bridge hidden at login.
  #
  # Three Windows traps live here, each of which silently breaks the launch:
  #
  # 1. ENCODING. WScript reads .vbs as ANSI, not UTF-8. This repo is at
  #    C:\<ae>, so a UTF-8 .vbs is decoded into mojibake and the launch dies
  #    with "The system cannot find the path specified" while reporting rc=0.
  #    The file must be UTF-16LE with a BOM -- hence the python helper.
  #
  # 2. TWO PATH FLAVOURS. WScript must OPEN bash.exe -> native form
  #    (C:\...\bash.exe). bash -lc must PARSE the script arg -> MSYS form
  #    (/c/.../rtx-bridge.sh). The native form as an argument makes bash eat
  #    the backslashes ("C:\a\b.sh" -> "C:ab.sh") and nothing runs.
  #
  # 3. THE NON-ASCII ROOT. Keeping the script path in MSYS form keeps the file
  #    free of non-ASCII paths, which is what makes trap 1 survivable.

  if [ -z "${APPDATA:-}" ]; then
    echo "APPDATA not set - not a Windows/MSYS shell"; return 1
  fi

  SU="$APPDATA/Microsoft/Windows/Start Menu/Programs/Startup"
  mkdir -p "$SU"
  VBS="$SU/rtx-bridge.vbs"

  BASH_EXE="$(cygpath -w "$(command -v bash)" 2>/dev/null || command -v bash)"
  SCRIPT_MSYS="$DIR/rtx-bridge.sh"
  HELPER="$DIR/rtx_bridge_startup.py"

  python "$(_native "$HELPER")" "$(_native "$VBS")" "$BASH_EXE" "$SCRIPT_MSYS"

  echo "  runs at next login - start now with:"
  echo "    wscript.exe \"$VBS\""
}

case "${1:-status}" in
  up)      cmd_up ;;
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  status)  cmd_status ;;
  logs)    cmd_logs ;;
  install) cmd_install ;;
  startup) cmd_startup ;;
  *) echo "usage: rtx-bridge.sh {up|start|stop|status|logs|install|startup}"; exit 2 ;;
esac
