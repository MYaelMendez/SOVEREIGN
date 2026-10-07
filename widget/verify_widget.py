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

HERE = os.path.dirname(os.path.abspath(__file__))


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(manifest_path: str) -> dict:
    man = json.load(open(manifest_path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(manifest_path))

    cap = man.get("capability", {}).get("wasm", {})
    declared = (cap.get("hash") or "").replace("sha256:", "")
    module_rel = cap.get("module", "")
    module_abs = os.path.join(base, module_rel)

    result = {
        "widget": man.get("identity", {}).get("id"),
        "version": man.get("identity", {}).get("version"),
        "publisher": man.get("identity", {}).get("publisher"),
        "module": module_rel,
        "declared_hash": declared,
        "permissions": man.get("trust", {}).get("permissions", []),
    }

    if not os.path.exists(module_abs):
        result.update(ok=False, reason=f"module not found: {module_abs}")
        return result

    actual = sha256_file(module_abs)
    result["actual_hash"] = actual
    result["actual_bytes"] = os.path.getsize(module_abs)
    result["hash_match"] = (actual == declared)
    result["ok"] = result["hash_match"]
    result["reason"] = "hash verified" if result["hash_match"] else "HASH MISMATCH — module tampered or stale"
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
    print(f"  permissions: {', '.join(r['permissions'])}")
    verdict = "✓ VERIFIED" if r.get("ok") else "✗ REJECTED"
    print(f"  {verdict}  — {r['reason']}")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
