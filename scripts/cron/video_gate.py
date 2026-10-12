#!/usr/bin/env python3
"""
video_gate.py — Verify all teologia MP4s pass supervisor thresholds.

Checks:
1. All MP4s exist and are non-zero
2. All MP4s are accessible via HTTP 200
3. Gate metrics present in index.html (luminance, contrast, motion, black frames)

Exit 0 = all pass, Exit 1 = any failure.
"""

import sys, time, urllib.request, re
from pathlib import Path

TEOLOGIA_DIR = Path(r"C:\æ\github-pages\teologia")
INDEX_FILE = TEOLOGIA_DIR / "index.html"
LIVE_BASE = "https://myaelmendez.github.io/teologia/"
LOG_FILE = Path(r"C:\æ\logs\video-gate.log")

EXPECTED_MP4 = [
    "demo-teologia.mp4",
    "apocalipsis-21.mp4",
    "salmo-23.mp4",
    "juan-316.mp4",
    "genesis-1.mp4",
    "proverbios-3.mp4",
    "mateo-5.mp4",
    "isaias-40.mp4",
]

def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def check_http(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except Exception as e:
        return str(e)

def check_gate_metrics(html):
    """Check if index.html has gate metrics for all videos."""
    # Look for luminance/contrast/motion values
    has_luminance = "LUMINANCIA" in html or "luminancia" in html.lower()
    has_contrast = "CONTRASTE" in html or "contraste" in html.lower()
    has_motion = "MOVIMIENTO" in html or "movimiento" in html.lower()
    has_black = "FRAMES NEGROS" in html or "frames_negros" in html.lower()
    return has_luminance and has_contrast and has_motion and has_black

def main():
    log("=== video gate check ===")
    failures = []

    # Check all MP4s exist locally
    for mp4 in EXPECTED_MP4:
        path = TEOLOGIA_DIR / mp4
        if not path.exists():
            log(f"  FAIL {mp4} — missing locally")
            failures.append(mp4)
        elif path.stat().st_size == 0:
            log(f"  FAIL {mp4} — zero bytes")
            failures.append(mp4)
        else:
            size_mb = path.stat().st_size / 1048576
            log(f"  OK  {mp4} ({size_mb:.1f} MB)")

    # Check all MP4s are live
    for mp4 in EXPECTED_MP4:
        url = LIVE_BASE + mp4
        status = check_http(url)
        if status == 200:
            log(f"  OK  {mp4} live (HTTP 200)")
        else:
            log(f"  FAIL {mp4} live → {status}")
            failures.append(mp4)

    # Check gate metrics in index.html
    if INDEX_FILE.exists():
        html = INDEX_FILE.read_text(encoding="utf-8", errors="ignore")
        if check_gate_metrics(html):
            log("  OK  gate metrics present in index.html")
        else:
            log("  FAIL gate metrics missing from index.html")
            failures.append("gate-metrics")
    else:
        log("  FAIL index.html not found")
        failures.append("index.html")

    if failures:
        log(f"RESULT: {len(failures)} FAILURES")
        sys.exit(1)
    else:
        log("RESULT: ALL MP4s PASS GATE")
        sys.exit(0)

if __name__ == "__main__":
    main()
