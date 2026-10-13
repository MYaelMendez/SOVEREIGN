#!/usr/bin/env bash
set -u
cd /c/æ
GPU="/c/gpu/Scripts/python.exe"
for n in 1-corpus 2-plataforma 3-ensenar; do
  echo "===== RENDER teo-$n ====="
  rm -f "studio/output/teo-$n-916.mp4"
  PID=$(cmd /c "netstat -ano | findstr :9333" 2>/dev/null | head -1 | awk '{print $NF}')
  if [ -n "${PID:-}" ] && [ "$PID" != "0" ]; then
    echo "  clearing stale CDP holder PID $PID"
    cmd /c "taskkill /PID $PID /F" >/dev/null 2>&1; sleep 3
  fi
  timeout 900 cmd /c "cd /d C:\æ\store\mp4-factory-app && node vidaeo-producer.js C:\æ\studio\specs\spec-teo-$n-916.json C:\æ\studio\output\teo-$n-916.mp4" 2>&1 | tail -6
  if [ -f "studio/output/teo-$n-916.mp4" ]; then
    echo "  --- gate ---"
    timeout 400 "$GPU" vidæo/vidæo.py verify "studio/output/teo-$n-916.mp4" 2>&1 | grep -E "PASS|FAIL" | head -1
    sha256sum "studio/output/teo-$n-916.mp4" | cut -d' ' -f1 | sed 's/^/  sha256: /'
    stat -c%s "studio/output/teo-$n-916.mp4" | sed 's/^/  bytes: /'
  else
    echo "  !! NO FILE for teo-$n"
  fi
done
echo "===== TEOLOGIA SERIES COMPLETE ====="
