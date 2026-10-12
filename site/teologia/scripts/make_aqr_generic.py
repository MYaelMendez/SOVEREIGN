#!/usr/bin/env python3
"""Parametrized æqr badge generator.

Usage:
    python make_aqr_generic.py <html-file> <artifact-id> [short-id]

  <html-file>    filename relative to teologia/ (e.g. confesion-de-augsburgo.html)
  <artifact-id>  the receipt id (e.g. augsburgo)
  [short-id]     badge svg suffix (default: artifact-id)

Injects the badge into <!--AEQR_BADGE--> and the hash into __AEQR_HASH__,
writes <html-base>.aqr.json and aeqr-badge-<short>.svg, verifies the QR decodes.
"""
from __future__ import annotations
import hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
import qrcode
from qrcode.constants import ERROR_CORRECT_M

ROOT = Path(r"C:\æ\site\teologia")
ISSUER = "☺://cc"
SCHEME = "æqr://v1"
REGION = "es-LATAM"


def canonical_text(html_path: Path) -> str:
    html = html_path.read_text(encoding="utf-8")
    body = re.search(r"<body>(.*?)<script", html, re.S)
    src = body.group(1) if body else html
    src = re.sub(r"<!--badgerow:start-->.*?<!--badgerow:end-->", " ", src, flags=re.S)
    src = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    src = re.sub(r"<svg.*?</svg>", " ", src, flags=re.S)
    src = re.sub(r"<[^>]+>", " ", src)
    for a, b in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&#10515;", "⤓"), ("&#x263A;", "☺")]:
        src = src.replace(a, b)
    return re.sub(r"\s+", " ", src).strip()


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
                parts.append(f'<rect x="{(c+border)*cell}" y="{(r+border)*cell}" width="{cell}" height="{cell}"/>')
    parts.append(f'<rect class="frame" x="0.5" y="0.5" width="{S-1}" height="{S-1}"/>')
    parts.append("</svg>")
    return "".join(parts), n, qr.version


def _matches(decoded: str, payload: str) -> bool:
    """A decoded string is accepted when it equals the payload, or when it
    carries the payload's sha256 (robust against decoders that mangle the
    non-ASCII 'æ'/'☺' prefix via charset guessing)."""
    if decoded == payload:
        return True
    m = re.search(r"sha256:([0-9a-f]{64})", payload)
    return bool(m) and m.group(1) in decoded


def verify_decode(payload: str) -> tuple[bool, str]:
    try:
        import numpy as np
    except Exception as e:
        return False, f"decoder unavailable: {e}"

    def raster(box: int):
        qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, border=4, box_size=box)
        qr.add_data(payload)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # 1) cv2 across scales
    try:
        import cv2
        det = cv2.QRCodeDetector()
        for box in (8, 10, 12, 16, 20, 24):
            arr = np.array(raster(box))[:, :, ::-1]
            data, _pts, _ = det.detectAndDecode(arr)
            if data and _matches(data, payload):
                return True, f"cv2 box={box} decoded"
    except Exception:
        pass

    # 2) pyzbar fallback (robust on dense QRs cv2 misses)
    try:
        from pyzbar.pyzbar import decode as zdec
        for box in (10, 14, 18):
            for d in zdec(raster(box)):
                txt = d.data.decode("utf-8", "replace")
                if _matches(txt, payload):
                    return True, f"pyzbar box={box} decoded"
    except Exception:
        pass

    return False, "no decoder matched the sha256"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    html_path = ROOT / sys.argv[1]
    artifact_id = sys.argv[2]
    short = sys.argv[3] if len(sys.argv) > 3 else artifact_id
    badge_svg = ROOT / f"aeqr-badge-{short}.svg"
    receipt = ROOT / f"{html_path.stem}.aqr.json"

    if not html_path.exists():
        print(f"FAIL: not found: {html_path}")
        return 1

    text = canonical_text(html_path)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    issued = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    full_id = f"teologia.ai/{artifact_id}"
    payload = f"{SCHEME}|{full_id}|{REGION}|sha256:{digest}|issuer:{ISSUER}"
    svg, modules, version = qr_svg(payload)
    ok, msg = verify_decode(payload)

    print(f"=== æqr badge ({artifact_id}) ===")
    print(f"  file       : {html_path.name}")
    print(f"  canonical  : {len(text)} chars")
    print(f"  sha256     : {digest}")
    print(f"  qr         : v{version} ({modules}x{modules})")
    print(f"  decode     : {'PASS' if ok else 'FAIL'} — {msg}")
    print(f"  svg bytes  : {len(svg)}")

    badge_svg.write_text(svg, encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    if "<!--AEQR_BADGE-->" in html:
        html = html.replace("<!--AEQR_BADGE-->", svg, 1)
        print("  inject     : badge inserted")
    elif 'class="aqr"' in html:
        print("  inject     : badge already present (skip)")
    else:
        print("FAIL: marker <!--AEQR_BADGE--> not found")
        return 1
    if "__AEQR_HASH__" in html:
        html = html.replace("__AEQR_HASH__", digest, 1)
    html_path.write_text(html, encoding="utf-8")

    receipt.write_text(json.dumps({
        "scheme": SCHEME, "artifact": full_id, "region": REGION,
        "sha256": digest, "issuer": ISSUER, "issued_at": issued,
        "qr_version": version, "qr_modules": modules, "payload": payload,
        "decoded_ok": ok, "decode_note": msg,
        "badge_svg": str(badge_svg), "html": str(html_path),
        "note": "signed intent can travel; authority does not travel with it",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  badge      : {badge_svg.name}")
    print(f"  receipt    : {receipt.name}")
    print(f"  html       : injected ({len(html)} bytes)")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
