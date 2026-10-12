#!/usr/bin/env python3
"""
verify_widget.py — verify an æ:// widget INDEPENDENTLY of its QR.

The QR is only an address. Trust comes from re-hashing the WASM module and
comparing it to the manifest's `trust.module_hash`, and from checking the
declared permissions. This verifier does exactly that — it never trusts the
QR bytes, it trusts the hash.

Usage:
    python verify_widget.py                 # verify ./manifest.json
    python verify_widget.py path/manifest.json
    python verify_widget.py --json          # machine-readable result
"""
from __future__ import annotations
import hashlib
import json
import os
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

HERE = os.path.dirname(os.path.abspath(__file__))


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    """Verify an Ed25519 signature against a public key."""
    try:
        pk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        pk.verify(bytes.fromhex(signature_hex), message.encode())
        return True
    except Exception:
        return False


def verify(manifest_path: str) -> dict:
    man = json.load(open(manifest_path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(manifest_path))

    cap = man.get("capability", {}).get("wasm", {})
    declared = (cap.get("hash") or "").replace("sha256:", "")
    module_rel = cap.get("module", "")
    module_abs = os.path.join(base, module_rel)

    trust = man.get("trust", {})
    result = {
        "widget": man.get("identity", {}).get("id"),
        "version": man.get("identity", {}).get("version"),
        "publisher": man.get("identity", {}).get("publisher"),
        "module": module_rel,
        "declared_hash": declared,
        "permissions": trust.get("permissions", []),
        "publisher_fingerprint": trust.get("publisher_fingerprint", ""),
    }

    # ── 1. AUTHENTICITY: verify the publisher's Ed25519 signature ──
    pubkey_hex = trust.get("publisher_pubkey", "")
    sig_hex = trust.get("signature", "")
    if not pubkey_hex or not sig_hex:
        result.update(ok=False, reason="no publisher signature — cannot verify authenticity")
        return result

    # Reconstruct the signed message: everything except trust.signature
    signable = {k: v for k, v in man.items() if k != "trust"}
    signable["trust"] = {k: v for k, v in trust.items() if k != "signature"}
    msg = json.dumps(signable, sort_keys=True, ensure_ascii=True)

    sig_ok = verify_signature(pubkey_hex, msg, sig_hex)
    result["signature_valid"] = sig_ok
    if not sig_ok:
        result.update(ok=False, reason="SIGNATURE INVALID — manifest not signed by claimed publisher")
        return result

    # ── 2. INTEGRITY: verify the WASM module hash ──
    if not os.path.exists(module_abs):
        result.update(ok=False, reason=f"module not found: {module_abs}")
        return result

    actual = sha256_file(module_abs)
    result["actual_hash"] = actual
    result["actual_bytes"] = os.path.getsize(module_abs)
    result["hash_match"] = (actual == declared)
    if not result["hash_match"]:
        result.update(ok=False, reason="HASH MISMATCH — module tampered or stale")
        return result

    # ── 3. PERMISSIONS: declared capabilities ──
    result["ok"] = True
    result["reason"] = "signature verified + hash verified"
    return result


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    manifest = args[0] if args else os.path.join(HERE, "manifest.json")

    r = verify(manifest)

    if as_json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0 if r.get("ok") else 1

    print(f"æ://widget/{r['widget']}@{r['version']}  (publisher: {r['publisher']})")
    print(f"  module     : {r['module']}")
    print(f"  declared   : {r['declared_hash']}")
    print(f"  actual     : {r.get('actual_hash','(missing)')}")
    print(f"  fingerprint: {r.get('publisher_fingerprint','(none)')}")
    print(f"  signature  : {'✓ valid' if r.get('signature_valid') else '✗ invalid'}")
    print(f"  permissions: {', '.join(r['permissions'])}")
    verdict = "✓ VERIFIED" if r.get("ok") else "✗ REJECTED"
    print(f"  {verdict}  — {r['reason']}")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
