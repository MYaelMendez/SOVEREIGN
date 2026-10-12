#!/usr/bin/env python3
"""æqr badge generator for the teologia.ai platform index page.

The platform badge is a constitutional aggregate over all five artifacts.
The hash is computed over a canonical platform manifest that lists each
artifact's actual SHA-256 of its HTML bytes on disk.
This is the æ:// canon: one badge, many surfaces, one root.

Truth rules:
  - the QR encodes a real payload (qrcode lib)
  - the QR is verified by decoding it back (cv2)
  - the hash is over the actual platform manifest bytes
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
INDEX = ROOT / "index.html"
BADGE_SVG = ROOT / "aeqr-badge-platform.svg"
RECEIPT = ROOT / "platform.aqr.json"
MANIFEST = ROOT / "platform-manifest.json"

ARTIFACT_ID = "teologia.ai/platform"
ISSUER = "☺://cc"
SCHEME = "æqr://v1"
REGION = "es-LATAM"

ARTIFACTS = [
    {"id": "orar",        "file": "una-manera-sencilla-de-orar.html"},
    {"id": "catecismo",   "file": "catecismo-menor.html"},
    {"id": "enchiridion", "file": "enchiridion.html"},
    {"id": "mayor",       "file": "catecismo-mayor.html"},
    {"id": "formula",     "file": "formula-de-concordia.html"},
    {"id": "libro",       "file": "libro-de-concordia.html"},
    {"id": "augsburgo",   "file": "confesion-de-augsburgo.html"},
    {"id": "apologia",    "file": "apologia-de-la-confesion.html"},
    {"id": "smalcalda",   "file": "articulos-de-smalcalda.html"},
    {"id": "tratado",     "file": "tratado-del-primado.html"},
    {"id": "tesis",       "file": "noventa-y-cinco-tesis.html"},
    {"id": "nobleza",     "file": "a-la-nobleza-cristiana.html"},
    {"id": "cautividad",  "file": "la-cautividad-babilonica.html"},
    {"id": "libertad",    "file": "la-libertad-cristiana.html"},
    {"id": "apostolico",  "file": "credo-apostolico.html"},
    {"id": "niceno",      "file": "credo-niceno.html"},
    {"id": "atanasio",    "file": "credo-atanasio.html"},
]


def canonical_manifest() -> tuple[str, str]:
    entries = []
    for a in ARTIFACTS:
        html_path = ROOT / a["file"]
        actual = hashlib.sha256(html_path.read_bytes()).hexdigest()
        entries.append({
            "file": a["file"],
            "sha256": actual,
            "sha256_prefix": actual[:16],
            "bytes": html_path.stat().st_size,
        })
    manifest = {
        "artifact": ARTIFACT_ID,
        "region": REGION,
        "issuer": ISSUER,
        "artifacts": entries,
    }
    manifest_json = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    return manifest_json, hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()


def qr_svg(payload: str, border: int = 2, cell: int = 4) -> tuple[str, int, int]:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, border=0, box_size=1)
    qr.add_data(payload)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    total = n + border * 2
    S = total * cell
    parts = [
        f'<svg class="aqr" viewBox="0 0 {S} {S}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="æqr platform badge">'
    ]
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
        import numpy as np
        import cv2
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
    if not INDEX.exists():
        print(f"FAIL: index not found: {INDEX}")
        return 1

    manifest_json, digest = canonical_manifest()
    issued = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = f"{SCHEME}|{ARTIFACT_ID}|{REGION}|sha256:{digest}|issuer:{ISSUER}"
    svg, modules, version = qr_svg(payload)
    ok, msg = verify_decode(payload)

    print("=== æqr badge (platform) ===")
    print(f"  artifact   : {ARTIFACT_ID}")
    print(f"  region     : {REGION}")
    print(f"  canonical  : {len(manifest_json)} chars (manifest JSON)")
    print(f"  sha256     : {digest}")
    print(f"  payload    : {payload[:72]}…")
    print(f"  qr version : {version}  ({modules}x{modules} modules)")
    print(f"  decode     : {'PASS' if ok else 'FAIL'} — {msg}")
    print(f"  svg bytes  : {len(svg)}")

    BADGE_SVG.write_text(svg, encoding="utf-8")
    MANIFEST.write_text(manifest_json, encoding="utf-8")

    # Inject into index.html: replace the hand-written placeholder SVG
    html = INDEX.read_text(encoding="utf-8")
    old_start = html.find('<svg class="aqr"')
    if old_start != -1:
        old_end = html.find('</svg>', old_start)
        if old_end != -1:
            old_end += len('</svg>')
            html = html[:old_start] + svg + html[old_end:]
            print("  inject     : platform badge replaced")
        else:
            print("  inject     : FAIL — could not find </svg> closing tag")
            return 1
    else:
        print("  inject     : FAIL — no existing aqr svg found")
        return 1

    INDEX.write_text(html, encoding="utf-8")

    receipt = {
        "scheme": SCHEME,
        "artifact": ARTIFACT_ID,
        "region": REGION,
        "sha256": digest,
        "issuer": ISSUER,
        "issued_at": issued,
        "qr_version": version,
        "qr_modules": modules,
        "payload": payload,
        "decoded_ok": ok,
        "decode_note": msg,
        "badge_svg": str(BADGE_SVG),
        "manifest": str(MANIFEST),
        "html": str(INDEX),
        "note": "platform manifest aggregates 5 devotional artifacts; "
                "signed intent can travel; authority does not travel with it",
    }
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n  badge      : {BADGE_SVG}")
    print(f"  receipt    : {RECEIPT}")
    print(f"  manifest   : {MANIFEST}")
    print(f"  html       : updated ({len(html)} bytes)")

    print("\n=== Artifact verification ===")
    for a in ARTIFACTS:
        actual = hashlib.sha256((ROOT / a["file"]).read_bytes()).hexdigest()
        print(f"  {a['file']:40s} sha256:{actual[:16]}…")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
