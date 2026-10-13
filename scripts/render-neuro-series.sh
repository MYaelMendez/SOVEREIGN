#!/usr/bin/env bash
# Render + gate the NEUROMITOSIS series (bond · haebbian · sovereignty).
# Tracked background job: one render exceeds a foreground window, and a killed
# producer orphans Chrome on :9333 which then breaks the NEXT render.
set -u
cd /c/æ
GPU="/c/gpu/Scripts/python.exe"

for n in 1-bond 2-haebbian 3-sovereignty; do
  echo "===== RENDER neuro-$n ====="
  rm -f "studio/output/neuro-$n-916.mp4"
  PID=$(cmd /c "netstat -ano | findstr :9333" 2>/dev/null | head -1 | awk '{print $NF}')
  if [ -n "${PID:-}" ] && [ "$PID" != "0" ]; then
    echo "  clearing stale CDP holder PID $PID"
    cmd /c "taskkill /PID $PID /F" >/dev/null 2>&1
    sleep 3
  fi
  timeout 900 cmd /c "cd /d C:\æ\store\mp4-factory-app && node vidaeo-producer.js C:\æ\studio\specs\spec-neuro-$n-916.json C:\æ\studio\output\neuro-$n-916.mp4" 2>&1 | tail -6

  if [ -f "studio/output/neuro-$n-916.mp4" ]; then
    echo "  --- gate ---"
    timeout 400 "$GPU" vidæo/vidæo.py verify "studio/output/neuro-$n-916.mp4" 2>&1 | grep -E "PASS|FAIL" | head -1
    sha256sum "studio/output/neuro-$n-916.mp4" | cut -d' ' -f1 | sed 's/^/  sha256: /'
    stat -c%s "studio/output/neuro-$n-916.mp4" | sed 's/^/  bytes: /'
  else
    echo "  !! NO FILE PRODUCED for neuro-$n"
  fi
done
echo "===== NEUROMITOSIS SERIES COMPLETE ====="
