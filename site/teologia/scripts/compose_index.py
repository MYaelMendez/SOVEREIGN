#!/usr/bin/env python3
"""Compose index.html = template + verified inline æqr badge at the marker.

The badge is the verified SVG (extracted from the previous page, 1201 rect ops,
payload sha256 cef95dab…). It is injected verbatim so the chip survives the rewrite.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(r"C:\æ\site\teologia")
TEMPLATE = ROOT / "_index_template.html"
BADGE = ROOT / "scripts" / "_platform_badge_inline.svg"
OUT = ROOT / "index.html"

tpl = TEMPLATE.read_text(encoding="utf-8")
badge = BADGE.read_text(encoding="utf-8")

if "<!--AEQR_BADGE-->" not in tpl:
    print("FAIL: marker <!--AEQR_BADGE--> not found in template")
    sys.exit(1)

html = tpl.replace("<!--AEQR_BADGE-->", badge, 1)
OUT.write_text(html, encoding="utf-8")

# ---- verification (precompute: f-strings cannot hold backslashes pre-3.12) ----
Q_AQR = 'class="aqr"'
Q_CARD = 'class="card"'
Q_ASK = 'button class="ai"'
n_badge = html.count(Q_AQR)
n_cards = html.count(Q_CARD)
n_ask = html.count(Q_ASK)
n_cdn = len(re.findall(r"cdn\.jsdelivr|unpkg\.com|esm\.run", html))
m = re.search(r"sha256:([0-9a-f]{64})", badge)
payload = (m.group(1)[:16] + "\u2026") if m else "MISSING"
has_wgsl = "@compute" in html
has_webllm = "./vendor/webllm/web-llm.js" in html
has_three = "./vendor/three.module.js" in html
n_div = html.count("<div") - html.count("</div>")

print("=== index.html composed ===")
print("  bytes            :", len(html.encode("utf-8")))
print("  badge svg        :", n_badge)
print("  badge rect ops   :", badge.count("<rect"))
print("  badge payload    :", payload)
print("  cards            :", n_cards)
print("  ask buttons      :", n_ask)
print("  webllm import    :", has_webllm)
print("  webgpu wgsl      :", has_wgsl)
print("  three importmap  :", has_three)
print("  cdn refs         :", n_cdn)
print("  unclosed divs    :", n_div)

ok = (n_badge == 1 and n_cards == 17 and n_ask == 17
      and has_wgsl and has_webllm and has_three and n_cdn == 0 and n_div == 0)
print("\n  RESULT           :", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 2)
