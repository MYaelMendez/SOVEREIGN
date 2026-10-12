#!/usr/bin/env python3
"""
qr_verify.py — Verify all QR badge URLs resolve to live 200 responses.

Reads qr_urls.txt, checks each URL, reports failures.
Exit 0 = all resolve, Exit 1 = any failure.
"""

import sys, time, urllib.request
from pathlib import Path

QR_URLS_FILE = Path(r"C:\æ\scripts\cron\qr_urls.txt")
LOG_FILE = Path(r"C:\æ\logs\qr-verify.log")

def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def check_url(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except Exception as e:
        return str(e)

def main():
    if not QR_URLS_FILE.exists():
        log("ERROR: qr_urls.txt not found")
        sys.exit(1)

    urls = [line.strip() for line in QR_URLS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    log(f"Checking {len(urls)} URLs...")

    failures = []
    for url in urls:
        status = check_url(url)
        if status == 200:
            log(f"  OK  {url}")
        else:
            log(f"  FAIL {url} → {status}")
            failures.append((url, status))

    if failures:
        log(f"RESULT: {len(failures)}/{len(urls)} FAILED")
        sys.exit(1)
    else:
        log(f"RESULT: ALL {len(urls)} URLs RESOLVE")
        sys.exit(0)

if __name__ == "__main__":
    main()
