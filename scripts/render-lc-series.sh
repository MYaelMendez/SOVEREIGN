#!/usr/bin/env bash
set -u
cd /c/æ
GPU="/c/gpu/Scripts/python.exe"
n="1-ad"
echo "===== RENDER lc-$n ====="
rm -f "studio/output/lc-$n-916.mp4"
timeout 900 cmd /c "cd /d C:\æ\store\mp4-factory-app && node vidaeo-producer.js C:\æ\studio\specs\spec-lc-$n-916.json C:\æ\studio\output\lc-$n-916.mp4" 2>&1 | tail -8
if [ -f "studio/output/lc-$n-916.mp4" ]; then
  echo "  --- gate ---"
  timeout 400 "$GPU" vidæo/vidæo.py verify "studio/output/lc-$n-916.mp4" 2>&1 | grep -E "PASS|FAIL" | head -1
  sha256sum "studio/output/lc-$n-916.mp4" | cut -d' ' -f1 | sed 's/^/  sha256: /'
  stat -c%s "studio/output/lc-$n-916.mp4" | sed 's/^/  bytes: /'
else
  echo "  !! NO FILE"
fi
echo "===== LONGCAT AD COMPLETE ====="
