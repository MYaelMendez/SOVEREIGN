#!/usr/bin/env python3
"""gen_batch_manifest.py — derive a 6000-task batch manifest with closed contracts.

    python gen_batch_manifest.py --count 6000 --wave-size 10 --out batch-manifest.json
    python gen_batch_manifest.py --count 6000 --wave-size 10 --out ... --dry-run

Nothing is executed here. The manifest is the contract the conductor audits
before spending a single agent. Derived, never hand-written.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

GATES = ["schema", "sha", "lesson_check", "receipt"]


def derive(count: int, wave_size: int, prefix: str) -> dict:
    tasks = []
    for i in range(count):
        tid = f"t_{i:05d}"
        wave = f"w{i // wave_size + 1:04d}"
        tasks.append({
            "task_id": tid,
            "wave": wave,
            "agent": f"{prefix}-{i:05d}",
            "inputs": [],                      # filled by the caller's adapter
            "outputs": [f"stage/{tid}/artifact.json"],
            "gates": list(GATES),
            "publish": False,                  # children NEVER publish
            "contract_sha": hashlib.sha256(
                f"{tid}|{wave}|{','.join(GATES)}|False".encode()).hexdigest()[:16],
        })
    return {
        "schema": "ae/fleet-batch/1",
        "batch_id": "b_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "derived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": count,
        "wave_size": wave_size,
        "waves": (count + wave_size - 1) // wave_size,
        "tasks": tasks,
        "note": "Derived contract. No task executes without a lease from fleet_wave.py claim.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=6000)
    ap.add_argument("--wave-size", type=int, default=10)
    ap.add_argument("--prefix", default="child")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.count <= 0 or a.wave_size <= 0:
        print(f"REFUSED: count={a.count} wave_size={a.wave_size} must both be positive", file=sys.stderr)
        return 1
    d = derive(a.count, a.wave_size, a.prefix)
    text = json.dumps(d, indent=2, ensure_ascii=False) + "\n"
    if a.dry_run:
        print(f"DRY-RUN: {d['count']} tasks, {d['waves']} waves, wave_size={d['wave_size']}")
        print(f"  first: {d['tasks'][0]}")
        print(f"  last:  {d['tasks'][-1]}")
        print(f"  bytes would be: {len(text):,}")
        return 0
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text, encoding="utf-8")
    print(f"wrote {a.out}: {d['count']} tasks / {d['waves']} waves / {len(text):,}B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
