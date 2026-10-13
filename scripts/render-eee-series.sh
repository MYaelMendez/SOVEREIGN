#!/usr/bin/env bash
# Render + gate the three-video ETHICS / ECONOMICS / ENGINEERING series.
# Run as a tracked background job: a single render exceeds a foreground timeout,
# and the producer dies mid-capture if the shell is killed.
set -u
cd /c/æ
PY="/c/Users/yaelm/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
GPU="/c/gpu/Scripts/python.exe"

for n in 1-ethics 2-economics 3-engineering; do
  echo "===== RENDER eee-$n ====="
  rm -f "studio/output/eee-$n-916.mp4"
  # clear any orphan holding the CDP port before each launch
  PID=$(cmd /c "netstat -ano | findstr :9333" 2>/dev/null | head -1 | awk '{print $NF}')
  if [ -n "${PID:-}" ]; then
    echo "  clearing stale CDP holder PID $PID"
    cmd /c "taskkill /PID $PID /F" >/dev/null 2>&1
    sleep 3
  fi
  timeout 900 cmd /c "cd /d C:\æ\store\mp4-factory-app && node vidaeo-producer.js C:\æ\studio\specs\spec-eee-$n-916.json C:\æ\studio\output\eee-$n-916.mp4" 2>&1 | tail -8

  if [ -f "studio/output/eee-$n-916.mp4" ]; then
    echo "  --- gate ---"
    timeout 400 "$GPU" vidæo/vidæo.py verify "studio/output/eee-$n-916.mp4" 2>&1 | grep -E "PASS|FAIL" | head -1
    sha256sum "studio/output/eee-$n-916.mp4" | cut -d' ' -f1 | sed 's/^/  sha256: /'
    stat -c%s "studio/output/eee-$n-916.mp4" | sed 's/^/  bytes: /'
  else
    echo "  !! NO FILE PRODUCED for eee-$n"
  fi
done
echo "===== SERIES RENDER COMPLETE ====="
