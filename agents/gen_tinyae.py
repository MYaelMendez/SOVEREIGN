#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_tinyae.py — compatibility shim.

The generator moved into tinyæ itself, where membership, measurement and the
surfaces live together. Keeping a second implementation here is how the family
ended up with two measurement regimes and two different answers.

    python gen_tinyae.py --out tinyae-registry.json
    python gen_tinyae.py --out ... --check
    python gen_tinyae.py --out ... --html tinyae.html
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(r"C:/æ")
sys.path.insert(0, str(ROOT / "tinyae"))
import tinyae  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--html", type=Path)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    if a.check:
        if not a.out.exists():
            print("STALE: registry missing", file=sys.stderr)
            return 1
        reg = json.loads(a.out.read_text(encoding="utf-8"))
        if reg.get("families") != len(tinyae.FAMILY):
            print("STALE: family count changed", file=sys.stderr)
            return 1
        if reg.get("schema") != tinyae.SCHEMA:
            print(f"STALE: schema {reg.get('schema')} != {tinyae.SCHEMA}",
                  file=sys.stderr)
            return 1
        print(f"OK current: {reg['families']} families")
        return 0

    reg = tinyae.derive()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    if a.html:
        a.html.write_text(tinyae.render_report(reg), encoding="utf-8")
    print(f"{reg['name']}: {reg['families']} families · {reg['green']} green · "
          f"{reg['not_green']} not green · {reg['flaky']} flaky")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
