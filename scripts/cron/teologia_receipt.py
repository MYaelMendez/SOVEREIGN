#!/usr/bin/env python3
"""
teologia_receipt.py — Update kænbæn genesis-chain with master receipt.

Called by teologia-webmaster-cron.bat after all sub-crons complete.
Args: --status PASS|FAIL --issues N
"""

import sys, json, hashlib, time, argparse
from pathlib import Path

GENESIS_FILE = Path(r"C:\æ\kænbæn\genesis-chain.json")
LOG_FILE = Path(r"C:\æ\logs\teologia-receipt.log")

def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", required=True, choices=["PASS", "FAIL"])
    parser.add_argument("--issues", type=int, default=0)
    args = parser.parse_args()

    receipt = {
        "type": "teologia-webmaster",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": args.status,
        "issues": args.issues,
        "surfaces": 19,
        "sub_crons": [
            "teologia_audit.py",
            "qr_verify.py",
            "video_gate.py",
            "freshness_check.py",
        ],
    }

    receipt["sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True).encode()
    ).hexdigest()[:16]

    # Load or create genesis chain
    if GENESIS_FILE.exists():
        chain = json.loads(GENESIS_FILE.read_text(encoding="utf-8"))
    else:
        chain = {"receipts": []}

    chain.setdefault("receipts", []).append(receipt)

    GENESIS_FILE.write_text(
        json.dumps(chain, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    log(f"Receipt logged: {args.status} (issues: {args.issues}) sha256:{receipt['sha256']}")
    print(f"Receipt logged: {args.status} sha256:{receipt['sha256']}")

if __name__ == "__main__":
    main()
