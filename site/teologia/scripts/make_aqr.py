#!/usr/bin/env python3
"""æqr badge generator — the chip on the pamphlet.

Canon: QR = scannable, verifiable, hash-chained. This builds a real QR that
encodes a verification payload over the pamphlet's canonical text, renders it
gold-on-void as inline SVG, injects it into the HTML, and writes a receipt.

Truth rules honoured here:
  - the QR is generated from a REAL matrix (qrcode lib), never a placeholder
  - the hash is computed over the pamphlet's canonical text, not a fake value
  - the badge is verified by decoding it back (cv2 if present)
  - if anything fails, we say so and exit non-zero
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_M

ROOT = Path(r"C:\æ\site\teologia")
HTML = ROOT / "una-manera-sencilla-de-orar.html"
BADGE_SVG = ROOT / "aeqr-badge.svg"
RECEIPT = ROOT / "una-manera-sencilla-de-orar.aqr.json"

ARTIFACT_ID = "teologia.ai/una-manera-sencilla-de-orar"
ISSUER = "☺://cc"
SCHEME = "æqr://v1"


# --------------------------------------------------------------------------
# 1. Canonical text — the thing the badge actually verifies
# --------------------------------------------------------------------------
def canonical_text() -> str:
    """Extract the pamphlet's canonical text deterministically from the HTML.

    Strips tags, collapses whitespace, drops the badge row (which contains the
    badge itself). Stable across renders: same words -> same hash.
    """
    html = HTML.read_text(encoding="utf-8")
    # isolate the body content
    body = re.search(r"<body>(.*?)<script", html, re.S)
    src = body.group(1) if body else html
    # drop the badge row (explicit markers) — it is container, not message
    src = re.sub(r"<!--badgerow:start-->.*?<!--badgerow:end-->", " ", src, flags=re.S)
    src = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    src = re.sub(r"<svg.*?</svg>", " ", src, flags=re.S)
    src = re.sub(r"<[^>]+>", " ", src)
    # unescape the few entities we use
    for a, b in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")]:
        src = src.replace(a, b)
    src = re.sub(r"\s+", " ", src).strip()
    return src


# --------------------------------------------------------------------------
# 2. QR matrix -> gold-on-void SVG (currentColor so print can re-theme it)
# --------------------------------------------------------------------------
def qr_svg(payload: str, border: int = 2, cell: int = 4) -> tuple[str, int, int]:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, border=0, box_size=1)
    qr.add_data(payload)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    total = n + border * 2
    S = total * cell

    parts = [f'<svg class="aqr" viewBox="0 0 {S} {S}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="æqr verification badge">']
    parts.append(f'<title>{payload}</title>')
    for r, row in enumerate(m):
        for c, dark in enumerate(row):
            if dark:
                x = (c + border) * cell
                y = (r + border) * cell
                parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}"/>')
    parts.append(f'<rect class="frame" x="0.5" y="0.5" width="{S-1}" height="{S-1}"/>')
    parts.append("</svg>")
    return "".join(parts), n, qr.version


# --------------------------------------------------------------------------
# 3. Verify: decode the matrix back (proves it is a real, readable QR)
# --------------------------------------------------------------------------
def verify_decode(payload: str) -> tuple[bool, str]:
    try:
        import numpy as np
        import cv2
        from qrcode.constants import ERROR_CORRECT_M as ECC
    except Exception as e:  # noqa: BLE001
        return False, f"decoder unavailable: {e}"

    qr = qrcode.QRCode(error_correction=ECC, border=4, box_size=10)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    arr = np.array(img)[:, :, ::-1]  # RGB -> BGR
    det = cv2.QRCodeDetector()
    data, _pts, _ = det.detectAndDecode(arr)
    if data == payload:
        return True, "decoded == payload"
    return False, f"decoded mismatch: {data[:60]!r}"


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    if not HTML.exists():
        print(f"FAIL: html not found: {HTML}")
        return 1

    text = canonical_text()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    issued = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = f"{SCHEME}|{ARTIFACT_ID}|sha256:{digest}|issuer:{ISSUER}"
    svg, modules, version = qr_svg(payload)

    ok, msg = verify_decode(payload)

    print("=== æqr badge ===")
    print(f"  artifact   : {ARTIFACT_ID}")
    print(f"  canonical  : {len(text)} chars")
    print(f"  sha256     : {digest}")
    print(f"  payload    : {payload[:72]}…")
    print(f"  qr version : {version}  ({modules}x{modules} modules)")
    print(f"  decode     : {'PASS' if ok else 'FAIL'} — {msg}")
    print(f"  svg bytes  : {len(svg)}")

    BADGE_SVG.write_text(svg, encoding="utf-8")

    # inject into the HTML (idempotent: marker gone on a re-run)
    html = HTML.read_text(encoding="utf-8")
    if "<!--AEQR_BADGE-->" in html:
        html = html.replace("<!--AEQR_BADGE-->", svg, 1)
        print("  inject     : badge inserted")
    elif 'class="aqr"' in html:
        print("  inject     : badge already present (skip)")
    else:
        print("FAIL: marker <!--AEQR_BADGE--> not found in html")
        return 1
    # the legible hash line under the badge
    if "__AEQR_HASH__" in html:
        html = html.replace("__AEQR_HASH__", digest, 1)
    HTML.write_text(html, encoding="utf-8")

    receipt = {
        "scheme": SCHEME,
        "artifact": ARTIFACT_ID,
        "sha256": digest,
        "issuer": ISSUER,
        "issued_at": issued,
        "qr_version": version,
        "qr_modules": modules,
        "payload": payload,
        "decoded_ok": ok,
        "decode_note": msg,
        "badge_svg": str(BADGE_SVG),
        "html": str(HTML),
        "note": "signed intent can travel; authority does not travel with it",
    }
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  badge      : {BADGE_SVG}")
    print(f"  receipt    : {RECEIPT}")
    print(f"  html       : injected ({len(html)} bytes)")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
