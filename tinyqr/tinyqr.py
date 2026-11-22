#!/usr/bin/env python3
"""tinyqr — the sovereign instrument for the QR chip.

tinyqr does NOT replace the QR infrastructure (qr_key_manager, contract_qr,
qr_server). It GOVERNS it: it proves the whole chain end to end —

    keypair → sign → encode → decode → verify

— and refuses where a link cannot be measured. The QR is law CANON 3 ("QR = the
chip"); this is the instrument that makes the chip auditable.

Invariants (tiny* family):
  1. doctor() signs FOR REAL. A chain that cannot sign is refused, not assumed.
  2. Every verb has a refusal path; the tests pin them.
  3. The contract is read FROM THE ARTIFACT (the PNG bytes, the signature).
  4. A receipt is a claim until re-run; grade() re-encodes and compares bytes.

Measured on this machine. Stdlib + cryptography + qrcode + pyzbar.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

AGENTS = Path(r"C:\æ\agents")
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

LEDGER = Path(os.environ.get("TINYQR_LEDGER", r"C:\æ\logs\tinyqr.jsonl"))
GENESIS = "0" * 64


def _qkm():
    try:
        return importlib.import_module("qr_key_manager")
    except Exception as exc:
        raise RuntimeError(f"qr_key_manager no cargable: {type(exc).__name__}: {exc}")


def _contract():
    try:
        return importlib.import_module("contract_qr")
    except Exception as exc:
        raise RuntimeError(f"contract_qr no cargable: {type(exc).__name__}: {exc}")


# ── doctor: sign for real, end to end ──────────────────────────────────────

def doctor() -> dict:
    """Prove the chain: keypair → sign → QR → decode → verify.

    Every step is measured. The first failure is reported; nothing is assumed.
    """
    out = {"ok": False, "checks": {}}
    try:
        qkm = _qkm()
    except Exception as exc:
        out["checks"]["modules"] = f"REFUSED: {exc}"
        return out
    out["checks"]["modules"] = "qr_key_manager + contract_qr cargables"

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    # 1. keypair (ephemeral — never written)
    try:
        sk = Ed25519PrivateKey.generate()
        pk = sk.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        priv = sk.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption()).hex()
        out["checks"]["keypair"] = f"ed25519 · pub {pk[:16]}…"
    except Exception as exc:
        out["checks"]["keypair"] = f"REFUSED: {type(exc).__name__}: {exc}"
        return out

    # 2. sign
    msg = "tinyqr-doctor:" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
    try:
        sig = sk.sign(msg.encode()).hex()
        out["checks"]["sign"] = f"ok · sig {sig[:16]}…"
    except Exception as exc:
        out["checks"]["sign"] = f"REFUSED: {type(exc).__name__}: {exc}"
        return out

    # 3. verify
    ok = qkm.verify_signature(pk, msg, sig)
    out["checks"]["verify"] = "ok" if ok else "REFUSED: signature did not verify"
    if not ok:
        return out

    # 4. encode → decode the signature payload (the chip itself)
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "sig.png"
        try:
            enc = qkm.encode_qr(json.dumps({"p": pk, "s": sig, "m": msg}),
                                filepath=png)
            out["checks"]["encode"] = f"ok · {enc.get('size')} · v{enc.get('version')}"
        except Exception as exc:
            out["checks"]["encode"] = f"REFUSED: {type(exc).__name__}: {exc}"
            return out
        try:
            dec = qkm.decode_qr(png)
        except Exception as exc:
            out["checks"]["decode"] = f"REFUSED: {type(exc).__name__}: {exc}"
            return out
        if not dec.get("valid"):
            out["checks"]["decode"] = f"REFUSED: {dec.get('error', 'no QR detected')}"
            return out
        out["checks"]["decode"] = "ok · roundtrip"
        # 5. the decoded payload must verify too — the artifact is the contract
        d = dec.get("data") or {}
        reok = qkm.verify_signature(d.get("p", ""), d.get("m", ""), d.get("s", ""))
        out["checks"]["artifact_verifies"] = "ok" if reok else "REFUSED: decoded payload does not verify"
        out["ok"] = bool(reok)

    out["note"] = "measured on this machine, not assumed"
    return out


# ── verbs ──────────────────────────────────────────────────────────────────

def sign(name: str, message: str) -> dict:
    try:
        r = _qkm().sign_with_key(name, message)
    except Exception as exc:
        return {"ok": False, "refusal": f"{type(exc).__name__}: {exc}"}
    if "error" in r:
        return {"ok": False, "refusal": r["error"]}
    return {"ok": True, "fingerprint": r.get("fingerprint"),
            "signature": r.get("signature"), "public_key": r.get("public_key")}


def verify(public_key: str, message: str, signature: str) -> dict:
    try:
        ok = _qkm().verify_signature(public_key, message, signature)
    except Exception as exc:
        return {"ok": False, "refusal": f"{type(exc).__name__}: {exc}"}
    if not ok:
        return {"ok": False, "refusal": "signature does not verify against that key"}
    return {"ok": True}


def decode(png: Path | str) -> dict:
    png = Path(png)
    if not png.exists():
        return {"ok": False, "refusal": f"no such file: {png}"}
    try:
        d = _qkm().decode_qr(png)
    except Exception as exc:
        return {"ok": False, "refusal": f"{type(exc).__name__}: {exc}"}
    if not d.get("valid"):
        return {"ok": False, "refusal": d.get("error", "no QR detected")}
    return {"ok": True, "format": d.get("format"), "data": d.get("data")}


def issue(kind: str, payload: dict, name: str | None = None) -> dict:
    """Emit a QR artifact for a payload. Reads the contract from the bytes."""
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "issue.png"
        try:
            enc = _qkm().encode_qr(json.dumps(payload, sort_keys=True), filepath=png)
        except Exception as exc:
            return {"ok": False, "refusal": f"{type(exc).__name__}: {exc}"}
        d = decode(png)
        if not d.get("ok"):
            return {"ok": False, "refusal": d.get("refusal")}
        sha = hashlib.sha256(png.read_bytes()).hexdigest()
        return {"ok": True, "filepath": str(png), "size": enc.get("size"),
                "version": enc.get("version"), "sha256": sha,
                "roundtrip": d.get("data") == payload}


def grade(payload: dict) -> dict:
    """Determinism: encode the same payload twice, compare PNG bytes."""
    with tempfile.TemporaryDirectory() as td:
        a, b = Path(td) / "a.png", Path(td) / "b.png"
        try:
            _qkm().encode_qr(json.dumps(payload, sort_keys=True), filepath=a)
            _qkm().encode_qr(json.dumps(payload, sort_keys=True), filepath=b)
        except Exception as exc:
            return {"ok": False, "refusal": f"{type(exc).__name__}: {exc}"}
        ha = hashlib.sha256(a.read_bytes()).hexdigest()
        hb = hashlib.sha256(b.read_bytes()).hexdigest()
        return {"ok": ha == hb, "deterministic": ha == hb,
                "sha256_a": ha, "sha256_b": hb,
                "note": "two encodes, byte-compared. A QR must be reproducible."}


# ── ledger ─────────────────────────────────────────────────────────────────

def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def ledger_append(decision: str, payload: dict) -> dict:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    recs = ledger_read()
    prev = recs[-1]["hash"] if recs else GENESIS
    r = {"decision": decision, "payload": payload, "prev": prev}
    r["hash"] = _sha(_canon(r))
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return r


def ledger_read() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def ledger_verify() -> dict:
    recs = ledger_read()
    prev = GENESIS
    for r in recs:
        body = {k: v for k, v in r.items() if k != "hash"}
        if r.get("prev") != prev or r.get("hash") != _sha(_canon(body)):
            return {"chain_ok": False, "broken_at": r.get("decision"), "records": len(recs)}
        prev = r["hash"]
    return {"chain_ok": True, "records": len(recs),
            "head": recs[-1]["hash"][:12] if recs else GENESIS[:12]}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="tinyqr", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    s = sub.add_parser("sign"); s.add_argument("name"); s.add_argument("message")
    v = sub.add_parser("verify"); v.add_argument("pub"); v.add_argument("message"); v.add_argument("sig")
    d = sub.add_parser("decode"); d.add_argument("png")
    i = sub.add_parser("issue"); i.add_argument("json_payload")
    g = sub.add_parser("grade"); g.add_argument("json_payload")
    sub.add_parser("ledger")
    a = ap.parse_args()

    if a.cmd == "doctor":
        r = doctor(); print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("doctor", {"ok": r["ok"]})
        return 0 if r["ok"] else 1
    if a.cmd == "sign":
        r = sign(a.name, a.message); print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    if a.cmd == "verify":
        r = verify(a.pub, a.message, a.sig); print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    if a.cmd == "decode":
        r = decode(a.png); print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
        return 0 if r.get("ok") else 1
    if a.cmd == "issue":
        r = issue("raw", json.loads(a.json_payload)); print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("issue", {"ok": r.get("ok"), "sha256": r.get("sha256")})
        return 0 if r.get("ok") else 1
    if a.cmd == "grade":
        r = grade(json.loads(a.json_payload)); print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("grade", {"deterministic": r.get("deterministic")})
        return 0 if r.get("ok") else 1
    if a.cmd == "ledger":
        print(json.dumps(ledger_verify(), ensure_ascii=False, indent=1))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
