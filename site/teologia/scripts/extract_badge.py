#!/usr/bin/env python3
"""Extract the verified inline æqr badge SVG from index.html so it survives a rewrite."""
import re, sys
from pathlib import Path

ROOT = Path(r"C:\æ\site\teologia")
INDEX = ROOT / "index.html"
OUT = ROOT / "scripts" / "_platform_badge_inline.svg"

src = INDEX.read_text(encoding="utf-8")
m = re.search(r'<svg class="aqr".*?</svg>', src, re.S)
if not m:
    print("FAIL: no inline badge svg found")
    sys.exit(1)
svg = m.group(0)
OUT.write_text(svg, encoding="utf-8")
payload = re.search(r"sha256:([0-9a-f]{64})", svg)
print(f"badge svg bytes : {len(svg)}")
print(f"rect ops        : {svg.count('<rect')}")
print(f"payload sha256  : {payload.group(1) if payload else 'NONE'}")
print(f"saved           : {OUT}")
