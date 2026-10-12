#!/usr/bin/env python3
"""
freshness_check.py — Git status + stale file detection for teologia.ai.

Checks:
1. Git working tree is clean (no uncommitted changes)
2. No files older than 7 days in teologia/ (stale content)
3. Local matches remote (no unpushed commits)

Exit 0 = fresh, Exit 1 = stale or dirty.
"""

import sys, time, subprocess
from pathlib import Path
from datetime import datetime, timedelta

GH_PAGES = Path(r"C:\æ\github-pages")
TEOLOGIA_DIR = GH_PAGES / "teologia"
LOG_FILE = Path(r"C:\æ\logs\freshness-check.log")
STALE_THRESHOLD_DAYS = 7

def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def run_git(args):
    result = subprocess.run(
        ["git"] + args,
        cwd=GH_PAGES,
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip(), result.returncode

def main():
    log("=== freshness check ===")
    failures = []

    # 1. Git status
    status, _ = run_git(["status", "--short"])
    if status:
        log(f"  DIRTY: git tree has uncommitted changes")
        for line in status.split("\n")[:10]:
            log(f"    {line}")
        failures.append("dirty-tree")
    else:
        log("  OK  git tree clean")

    # 2. Stale file detection
    now = datetime.now()
    stale_files = []
    if TEOLOGIA_DIR.exists():
        for f in TEOLOGIA_DIR.iterdir():
            if f.is_file():
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                age_days = (now - mtime).days
                if age_days > STALE_THRESHOLD_DAYS:
                    stale_files.append((f.name, age_days))

    if stale_files:
        log(f"  STALE: {len(stale_files)} files older than {STALE_THRESHOLD_DAYS} days")
        for name, age in stale_files[:10]:
            log(f"    {name} ({age} days)")
        failures.append("stale-files")
    else:
        log(f"  OK  all files newer than {STALE_THRESHOLD_DAYS} days")

    # 3. Unpushed commits
    local, _ = run_git(["log", "origin/gh-pages..HEAD", "--oneline"])
    if local:
        log(f"  UNPUSHED: {len(local.split(chr(10)))} commits not on origin/gh-pages")
        failures.append("unpushed")
    else:
        log("  OK  no unpushed commits")

    if failures:
        log(f"RESULT: STALE — {len(failures)} issues")
        sys.exit(1)
    else:
        log("RESULT: FRESH")
        sys.exit(0)

if __name__ == "__main__":
    main()
