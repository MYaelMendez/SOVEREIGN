#!/usr/bin/env python3
"""æqr badge generator for catecismo-menor.html — same pattern as make_aqr.py."""
from __future__ import annotations
import hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
import qrcode
from qrcode.constants import ERROR_CORRECT_M

ROOT = Path(r"C:\æ\site\teologia")
HTML = ROOT / "catecismo-menor.html"
BADGE_SVG = ROOT / "aeqr-badge-catecismo.svg"
RECEIPT = ROOT / "catecismo-menor.aqr.json"

ARTIFACT_ID = "teologia.ai/catecismo-menor"
ISSUER = "☺://cc"
SCHEME = "æqr://v1"
REGION = "es-LATAM"


def canonical_text() -> str:
    html = HTML.read_text(encoding="utf-8")
    body = re.search(r"<body>(.*?)<script", html, re.S)
    src = body.group(1) if body else html
    src = re.sub(r"<!--badgerow:start-->.*?<!--badgerow:end-->", " ", src, flags=re.S)
    src = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    src = re.sub(r"<svg.*?</svg>", " ", src, flags=re.S)
    src = re.sub(r"<[^>]+>", " ", src)
    for a, b in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&#10515;", "⤓"), ("&#x263A;", "☺")]:
        src = src.replace(a, b)
    src = re.sub(r"\s+", " ", src).strip()
    return src


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


def verify_decode(payload: str) -> tuple[bool, str]:
    try:
        import numpy as np, cv2
        from qrcode.constants import ERROR_CORRECT_M as ECC
    except Exception as e:
        return False, f"decoder unavailable: {e}"
    qr = qrcode.QRCode(error_correction=ECC, border=4, box_size=10)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    arr = np.array(img)[:, :, ::-1]
    det = cv2.QRCodeDetector()
    data, _pts, _ = det.detectAndDecode(arr)
    if data == payload:
        return True, "decoded == payload"
    return False, f"decoded mismatch: {data[:60]!r}"


def main() -> int:
    if not HTML.exists():
        print(f"FAIL: html not found: {HTML}")
        return 1
    text = canonical_text()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    issued = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = f"{SCHEME}|{ARTIFACT_ID}|{REGION}|sha256:{digest}|issuer:{ISSUER}"
    svg, modules, version = qr_svg(payload)
    ok, msg = verify_decode(payload)
    print("=== æqr badge (catecismo) ===")
    print(f"  artifact   : {ARTIFACT_ID}")
    print(f"  region     : {REGION}")
    print(f"  canonical  : {len(text)} chars")
    print(f"  sha256     : {digest}")
    print(f"  payload    : {payload[:72]}…")
    print(f"  qr version : {version}  ({modules}x{modules} modules)")
    print(f"  decode     : {'PASS' if ok else 'FAIL'} — {msg}")
    print(f"  svg bytes  : {len(svg)}")
    BADGE_SVG.write_text(svg, encoding="utf-8")
    html = HTML.read_text(encoding="utf-8")
    if "<!--AEQR_BADGE-->" in html:
        html = html.replace("<!--AEQR_BADGE-->", svg, 1)
        print("  inject     : badge inserted")
    elif 'class="aqr"' in html:
        print("  inject     : badge already present (skip)")
    else:
        print("FAIL: marker <!--AEQR_BADGE--> not found in html")
        return 1
    if "__AEQR_HASH__" in html:
        html = html.replace("__AEQR_HASH__", digest, 1)
    HTML.write_text(html, encoding="utf-8")
    receipt = {
        "scheme": SCHEME, "artifact": ARTIFACT_ID, "region": REGION,
        "sha256": digest, "issuer": ISSUER, "issued_at": issued,
        "qr_version": version, "qr_modules": modules,
        "payload": payload, "decoded_ok": ok, "decode_note": msg,
        "badge_svg": str(BADGE_SVG), "html": str(HTML),
        "note": "signed intent can travel; authority does not travel with it",
    }
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  badge      : {BADGE_SVG}")
    print(f"  receipt    : {RECEIPT}")
    print(f"  html       : injected ({len(html)} bytes)")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
