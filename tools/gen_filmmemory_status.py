#!/usr/bin/env python3
"""gen_filmmemory_status.py — derive filmmemory-status.json from the ledger.

Same discipline as gen_qr_inventory.py / gen_capability_manifest.py:
the catalog is DERIVED, never hand-written. Source of truth is the
hash-chained tinyFILMMEMORY ledger; re-measured and recovered claims stay
distinct (RECOVERED IS NOT RE-MEASURED).

    python tools/gen_filmmemory_status.py            # write + mirror
    python tools/gen_filmmemory_status.py --check    # exit 1 if stale

The verify call re-hashes every cited film still on disk. Drift and absent
are reported, never silently dropped. A broken ledger chain is REFUSED.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:/æ")
TFM_DIR = ROOT / "tinyfilmmemory"
LEDGER = ROOT / "logs/filmmemory/ledger.jsonl"
OUT = ROOT / "github-pages/filmmemory-status.json"
MIRROR = ROOT / "site/filmmemory-status.json"

sys.path.insert(0, str(TFM_DIR))
import tinyfilmmemory as tfm  # noqa: E402  (stdlib, zero tokens, deterministic)


def derive() -> dict:
    v = tfm.verify(LEDGER)          # re-hash cited films + chain check
    if not v.get("ok"):
        # Do not publish a false GREEN. Emit an honest RED surface instead.
        return {
            "schema": "ae/filmmemory-status/1",
            "ok": False,
            "refused": True,
            "reason": str(v.get("reason") or v.get("chain", {}).get("reason") or "verify failed"),
            "source": "tinyFILMMEMORY ledger (chain check failed)",
        }
    recs = tfm.read_ledger(LEDGER)
    kinds = dict(Counter(r.get("kind") for r in recs))
    mk = dict(Counter(r.get("measurement_kind") for r in recs))
    films = [r for r in recs if r.get("kind") == "film"]
    defects = [r["title"] for r in films if r.get("results", {}).get("defect")]
    chain = v["chain"]
    return {
        "schema": "ae/filmmemory-status/1",
        "ok": True,
        "source": "tinyFILMMEMORY ledger — re-hashed from delivered bytes",
        "chain_ok": chain["ok"],
        "chain_length": chain["length"],
        "chain_head": chain["head"],
        "films": len(films),
        "films_checked": v["films_checked"],
        "drift": v["drift"],
        "absent": v["absent"],
        "kinds": kinds,
        "measurement_kinds": mk,
        "re_measured": mk.get("re_measured", 0),
        "recovered": mk.get("recovered", 0),
        "defects": defects,
        "note": "RECOVERED IS NOT RE-MEASURED. Absent artifact is honest; drift means bytes changed since sealing.",
    }


def render(d: dict) -> str:
    return json.dumps(d, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="derive filmmemory-status.json from ledger")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = render(derive())
    if a.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"STALE or MISSING: {OUT.name} — regenerate", file=sys.stderr)
            return 1
        print(f"OK: {OUT.name} is current")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    MIRROR.write_text(text, encoding="utf-8")
    print(f"  mirrored -> {MIRROR}")
    d = json.loads(text)
    print(f"  chain_ok={d.get('chain_ok')} films={d.get('films')} "
          f"drift={len(d.get('drift', []))} recovered={d.get('recovered')} "
          f"defects={len(d.get('defects', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
