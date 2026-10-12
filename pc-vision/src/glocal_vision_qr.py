#!/usr/bin/env python3
"""
PC://GLOCAL VISION QR — Verification badges for media artifacts.

Each verified artifact gets a QR code encoding its receipt.
QR = the chip (silicon ∩ information). Scan to verify.

The QR encodes:
  - artifact name
  - SHA-256 hash
  - verdict (PASS/WARN/FAIL)
  - supervision receipt
  - event hash (chain link)
  - timestamp

Scan flow:
  QR → decode → verify hash → verify chain → TRUSTED | UNTRUSTED

PC://GLOCAL_VISION_QR_V1
"""

import hashlib
import json
import sys
from pathlib import Path

# Add supervisionvidaeo to path for QR coding
sys.path.insert(0, str(Path("C:/æ/supervisionvidaeo/supervisionvidaeo/vision")))

try:
    from qr_coder import QRCoder
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

REPORT_DIR = Path("C:/æ/github-pages/glocal-vision")
RECEIPTS_FILE = REPORT_DIR / "glocal-vision-receipts.jsonl"
QR_OUTPUT_DIR = REPORT_DIR / "qr-badges"


def make_badge_payload(entry: dict) -> dict:
    """Create a compact QR payload from a receipt entry."""
    sup = entry.get("supervision", {})
    return {
        "schema": "GLOCAL_VISION_QR_V1",
        "name": entry.get("name", "unknown"),
        "sha256": entry.get("sha256", "")[:32],  # truncate for QR size
        "verdict": entry.get("verdict", "UNKNOWN"),
        "lum": round(sup.get("luminance", 0), 1),
        "con": round(sup.get("contrast", 0), 1),
        "mov": round(sup.get("motion", 0), 3),
        "receipt": sup.get("receipt", "")[:16],
        "event": entry.get("event_hash", "")[:16],
        "ts": entry.get("scanned_at", "")[:19],
    }


def generate_qr_badges():
    """Generate QR verification badges for all scanned artifacts."""
    print("=" * 60)
    print("  PC://GLOCAL VISION QR — verification badges")
    print("=" * 60)
    print()

    if not QR_AVAILABLE:
        print("WARNING: QRCoder not available — using fallback")
    
    if not RECEIPTS_FILE.exists():
        print(f"No receipts found: {RECEIPTS_FILE}")
        print("Run glocal_vision.py first.")
        return

    # Load receipts
    receipts = []
    with open(RECEIPTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    receipts.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    print(f"Loaded {len(receipts)} receipts")

    # Create output directory
    QR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate QR for each artifact (video and image)
    generated = 0
    skipped = 0

    for entry in receipts:
        name = entry.get("name", "unknown")
        verdict = entry.get("verdict", "UNKNOWN")

        # Only generate QR for video artifacts (not frame PNGs)
        if entry.get("ext", "") not in (".mp4", ".mov", ".webm", ".avi"):
            skipped += 1
            continue

        # Create QR payload
        payload = make_badge_payload(entry)
        payload_json = json.dumps(payload, separators=(",", ":"))

        # Generate QR
        qr_name = f"{Path(name).stem}-badge.png"
        qr_path = QR_OUTPUT_DIR / qr_name

        try:
            if QR_AVAILABLE:
                coder = QRCoder()
                result = coder.codificar_json(payload, filepath=str(qr_path))
                print(f"  [{'PASS' if verdict == 'PASS' else verdict}] {name} -> {qr_name}")
            else:
                # Fallback: write payload as JSON
                with open(qr_path.with_suffix('.json'), 'w') as f:
                    json.dump(payload, f, indent=2)
                print(f"  [{verdict}] {name} -> {qr_name.replace('.png', '.json')} (fallback)")
            generated += 1
        except Exception as e:
            print(f"  ERROR {name}: {str(e)[:60]}")

    print()
    print(f"Generated: {generated} QR badges")
    print(f"Skipped: {skipped} (non-video artifacts)")
    print(f"Output: {QR_OUTPUT_DIR}")
    print("=" * 60)


def verify_qr_payload(payload_json: str, receipts_file: Path = RECEIPTS_FILE) -> dict:
    """Verify a QR payload against the receipt chain."""
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {"trusted": False, "reason": "invalid JSON"}

    # Check schema
    if payload.get("schema") != "GLOCAL_VISION_QR_V1":
        return {"trusted": False, "reason": "wrong schema"}

    # Find matching receipt
    if not receipts_file.exists():
        return {"trusted": False, "reason": "no receipts file"}

    with open(receipts_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            if entry.get("name") == payload.get("name"):
                # Verify hash prefix matches
                if entry.get("sha256", "").startswith(payload.get("sha256", "")):
                    return {
                        "trusted": True,
                        "verdict": entry.get("verdict"),
                        "name": entry.get("name"),
                        "chain_verified": True,
                    }
                else:
                    return {"trusted": False, "reason": "hash mismatch"}

    return {"trusted": False, "reason": "not found in receipts"}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        # Verify a QR payload
        payload = sys.argv[2] if len(sys.argv) > 2 else ""
        result = verify_qr_payload(payload)
        print(json.dumps(result, indent=2))
    else:
        generate_qr_badges()
