#!/usr/bin/env python3
"""
PC://GLOCAL VISION — periodic media trust scan.

Scans all media artifacts across the glocal network, verifies each with
SupervisorVideo / deterministic CV, and produces hash-chained receipts.

Surfaces scanned:
  - C:/æ/github-pages/*.mp4           (truth surface videos)
  - C:/æ/threejs-curriculo/out/*.mp4  (render pipeline output)
  - C:/æ/github-pages/aipodcast_me/   (media hub assets)

For each artifact:
  1. ffprobe metadata (codec, resolution, duration, bitrate)
  2. SupervisorVideo gate (luminance, contrast, motion, black frames)
  3. SHA-256 hash of the file
  4. Evidence Bus receipt (hash-chained)
  5. Verdict: PASS | WARN | FAIL | REFUSED

Output: glocal-vision-report.json + glocal-vision-receipts.jsonl
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──
FFPROBE = "C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-7.1-nvenc/bin/ffprobe.exe"
VIDAO_PY = "C:/æ/vidæo/vidæo.py"
GPU_PY = "C:/gpu/Scripts/python.exe"
REPORT_DIR = Path("C:/æ/github-pages/glocal-vision")

SCAN_DIRS = [
    Path("C:/æ/github-pages"),
    Path("C:/æ/threejs-curriculo/out"),
    Path("C:/æ/github-pages/aipodcast_me"),
]

VIDEO_EXTS = {".mp4", ".mov", ".webm", ".avi"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

GENESIS_HASH = hashlib.sha256(b"GLOCAL_VISION_GENESIS").hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ffprobe_meta(path: Path) -> dict:
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries",
             "stream=codec_name,width,height,duration,nb_frames,bit_rate",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(r.stdout)
        streams = data.get("streams", [])
        return streams[0] if streams else {}
    except Exception as e:
        return {"error": str(e)[:100]}


def supervisor_verify(path: Path) -> dict:
    """Run SupervisorVideo gate on a video artifact."""
    try:
        r = subprocess.run(
            [GPU_PY, VIDAO_PY, "verify", str(path)],
            capture_output=True, text=True, timeout=120,
        )
        # Parse JSON from output (multi-line block)
        import re
        json_match = re.search(r'\{.*\}', r.stdout, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {"pass": False, "error": "no JSON in output", "raw": r.stdout[:200]}
    except Exception as e:
        return {"pass": False, "error": str(e)[:100]}


def scan_artifact(path: Path, prev_hash: str) -> dict:
    """Scan a single media artifact and produce a receipt."""
    file_hash = sha256_file(path)
    ext = path.suffix.lower()
    is_video = ext in VIDEO_EXTS

    entry = {
        "path": str(path),
        "name": path.name,
        "ext": ext,
        "size_bytes": path.stat().st_size,
        "sha256": file_hash,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "previous_hash": prev_hash,
    }

    if is_video:
        meta = ffprobe_meta(path)
        entry["ffprobe"] = {k: meta.get(k) for k in
                            ("codec_name", "width", "height", "duration", "nb_frames", "bit_rate")}

        verdict = supervisor_verify(path)
        entry["supervision"] = {
            "pass": verdict.get("calidad") == "PASS" or verdict.get("pass", False),
            "luminance": verdict.get("luminancia_media", 0),
            "contrast": verdict.get("contraste_medio", 0),
            "motion": verdict.get("movimiento_medio", 0),
            "black_frames": verdict.get("frames_negros", 0),
            "receipt": verdict.get("receipt", ""),
            "reasons": verdict.get("razones", []),
        }

        if entry["supervision"]["pass"]:
            entry["verdict"] = "PASS"
        elif entry["supervision"]["black_frames"] > 0:
            entry["verdict"] = "FAIL"
        else:
            entry["verdict"] = "WARN"
    else:
        entry["verdict"] = "INFO"  # images get hash only

    # Compute event hash (chain link)
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    entry["event_hash"] = hashlib.sha256(canonical.encode()).hexdigest()

    return entry


def run_scan():
    """Scan all media artifacts across glocal surfaces."""
    print("=" * 60)
    print("  PC://GLOCAL VISION — periodic media trust scan")
    print("=" * 60)
    print()

    artifacts = []
    skip_dirs = {'-frames', 'node_modules', '.git', 'glocal-vision', 'vendor', 'assets'}
    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for ext in VIDEO_EXTS | IMAGE_EXTS:
            for f in scan_dir.rglob(f'*{ext}'):
                # Skip frame directories and vendor assets
                parts = f.parts
                if any(skip in p for p in parts for skip in skip_dirs):
                    continue
                artifacts.append(f)

    # Deduplicate and limit
    seen = set()
    unique = []
    for a in artifacts:
        key = str(a.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(a)

    print(f"Found {len(unique)} media artifacts")
    print()

    receipts = []
    prev_hash = GENESIS_HASH
    verdicts = {"PASS": 0, "WARN": 0, "FAIL": 0, "INFO": 0}

    for artifact in unique:
        try:
            entry = scan_artifact(artifact, prev_hash)
            receipts.append(entry)
            prev_hash = entry["event_hash"]
            verdicts[entry["verdict"]] = verdicts.get(entry["verdict"], 0) + 1

            status = entry["verdict"]
            icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "INFO": "○"}.get(status, "?")
            print(f"  {icon} [{status}] {entry['name']} ({entry['size_bytes'] // 1024} KB)")

            if "supervision" in entry and entry["supervision"].get("luminance"):
                s = entry["supervision"]
                print(f"      lum={s['luminance']:.1f} con={s['contrast']:.1f} mov={s['motion']:.3f} black={s['black_frames']}")

        except Exception as e:
            print(f"  ✗ [ERROR] {artifact.name}: {str(e)[:80]}")

    print()
    print(f"Verdicts: {verdicts}")
    print(f"Chain length: {len(receipts)}")
    print(f"Final receipt: {prev_hash[:32]}")

    # ── Write report ──
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "schema": "PC://GLOCAL_VISION_V1",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "total_artifacts": len(unique),
        "verdicts": verdicts,
        "chain_length": len(receipts),
        "final_receipt": prev_hash,
        "genesis": GENESIS_HASH[:32],
        "surfaces": [str(d) for d in SCAN_DIRS],
    }

    report_path = REPORT_DIR / "glocal-vision-report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    receipts_path = REPORT_DIR / "glocal-vision-receipts.jsonl"
    with open(receipts_path, "w", encoding="utf-8") as f:
        for r in receipts:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print()
    print(f"Report:  {report_path}")
    print(f"Receipts: {receipts_path}")
    print("=" * 60)

    return report


if __name__ == "__main__":
    run_scan()
