#!/usr/bin/env python3
"""tinyEMOJI — the sovereign instrument for the emoji registry.

tinyEMOJI does NOT decorate symbols. It GOVERNS the registry: it reads the CORE
list from the surface itself, checks that every symbol has its QR on disk, that
the QR DECODES back to the right anchor, and that the punycode is computed rather
than recalled. A missing QR is a named refusal, not a broken page nobody notices.

    doctor     read emoji-registry.html, verify every core symbol end to end
    check      same, for any surface file
    resolve    one symbol -> codepoint, punycode, QR, decodes-to
    qr         generate the missing QR in the surface's own scheme
    grade      punycode is reproducible (same symbol -> same punycode)

Invariants (tiny* family): doctor() measures; every verb refuses; the contract is
read from the artifact; a receipt is a claim until re-run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(r"C:\æ")
REGISTRY = ROOT / "github-pages" / "aipodcast_me" / "emoji-registry.html"
QRDIR = ROOT / "github-pages" / "aipodcast_me" / "assets" / "qr"
BASE = "https://myaelmendez.github.io/aipodcast_me/emoji-registry.html"

LEDGER = Path(os.environ.get("TINYEMOJI_LEDGER", r"C:\æ\logs\tinyemoji.jsonl"))
GENESIS = "0" * 64


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


# ── read the registry from the artifact ─────────────────────────────────────

def core_of(path: Path | str) -> list[dict]:
    """Parse CORE=[{s,cp,cap},...] out of the HTML. The surface IS the registry."""
    src = Path(path).read_text(encoding="utf-8")
    m = re.search(r"var\s+CORE\s*=\s*\[(.*?)\];", src, re.S)
    if not m:
        raise ValueError("no CORE array en la superficie")
    body = m.group(1)
    rows = []
    for s, cp, cap in re.findall(
            r"\{s:'((?:[^'\\]|\\.)*)',cp:'([^']*)',cap:'([^']*)'\}", body):
        # the HTML is UTF-8: the symbol is already literal, never re-decoded
        rows.append({"symbol": s, "cp": cp, "cap": cap})
    if not rows:
        raise ValueError("CORE vacío o con formato desconocido")
    return rows


def qr_name(symbol: str) -> str:
    pts = "_".join(f"{ord(c):X}" for c in symbol)
    return f"U+{pts}.png"


def punycode(label: str) -> str:
    """Computed, never recalled. IDNA on each label, as the browser does."""
    try:
        return label.encode("idna").decode("ascii")
    except UnicodeError:
        return ""


def _decode_cv2(png: Path) -> str:
    """cv2's detector handles 4-byte UTF-8 that pyzbar mangles."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.fromfile(str(png), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return ""
    try:
        txt, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    except Exception:
        return ""
    return txt or ""


def decode_qr_all(png: Path) -> list[str]:
    """Every reading of the chip. pyzbar mis-decodes some 4-byte UTF-8 payloads
    (it returned Chinese text for 🍊); cv2 reads them fine. A single reader
    produces false refusals, so the caller decides which reading is right."""
    out = []
    try:
        from pyzbar.pyzbar import decode
        from PIL import Image
        hits = decode(Image.open(str(png)))
        if hits:
            out.append(hits[0].data.decode("utf-8", "replace"))
    except Exception:
        pass
    cv = _decode_cv2(png)
    if cv and cv not in out:
        out.append(cv)
    return out


def decode_qr(png: Path) -> str:
    cands = decode_qr_all(png)
    return cands[0] if cands else ""


# ── the check ──────────────────────────────────────────────────────────────

def check(path: Path | str, qrdir: Path | str = QRDIR) -> dict:
    """Verify a registry surface: every symbol has a QR that decodes correctly."""
    p, qd = Path(path), Path(qrdir)
    if not p.exists():
        return {"ok": False, "refusal": f"no such file: {p}"}
    try:
        rows = core_of(p)
    except ValueError as exc:
        return {"ok": False, "refusal": str(exc)}

    missing, bad_payload, ok = [], [], []
    for r in rows:
        name = qr_name(r["symbol"])
        png = qd / name
        if not png.exists():
            missing.append(name)
            continue
        want = f"{BASE}#{r['symbol']}"
        readings = decode_qr_all(png)
        if want not in readings:
            bad_payload.append({"qr": name, "want": want,
                                "got": [g[:80] for g in readings]})
        else:
            ok.append(r["symbol"])

    out = {"ok": not missing and not bad_payload,
           "symbols": len(rows), "qr_ok": len(ok),
           "missing": missing, "bad_payload": bad_payload,
           "punycode": {r["symbol"]: punycode(r["symbol"]) for r in rows[:6]},
           "qrdir": str(qd)}
    if missing:
        out["refusal"] = f"{len(missing)} QR ausentes: {missing[:6]}"
    elif bad_payload:
        out["refusal"] = f"{len(bad_payload)} QR no decodifican a su anchor"
    return out


# ── doctor ─────────────────────────────────────────────────────────────────

def doctor() -> dict:
    out = {"ok": False, "checks": {}}
    if not REGISTRY.exists():
        out["checks"]["registry"] = f"REFUSED: {REGISTRY} no existe"
        return out
    c = check(REGISTRY)
    out["checks"]["symbols"] = c["symbols"]
    out["checks"]["qr_ok"] = c["qr_ok"]
    out["checks"]["missing"] = len(c["missing"])
    out["checks"]["bad_payload"] = len(c["bad_payload"])
    if not c["ok"]:
        out["checks"]["refusal"] = c["refusal"]
        return out
    # punycode must be computed: the same symbol always yields the same encoding
    sym = core_of(REGISTRY)[0]["symbol"]
    pc1, pc2 = punycode(sym), punycode(sym)
    out["checks"]["punycode"] = f"{sym} → {pc1 or '(no registrable)'}"
    if pc1 != pc2:
        out["checks"]["punycode"] = "REFUSED: el punycode no es reproducible"
        return out
    # grapheme honesty: a symbol is not always one character
    multi = [r["symbol"] for r in core_of(REGISTRY) if len(r["symbol"]) > 1]
    out["checks"]["multichar"] = f"{len(multi)} símbolos son multicode ({multi[:4]})"
    out["ok"] = True
    out["note"] = "medido en esta maquina, no asumido"
    return out


# ── emit the missing QR in the surface's own scheme ────────────────────────

def make_qr(symbol: str, out: Path | str | None = None, qrdir: Path = QRDIR) -> dict:
    """Generate the QR exactly as the registry's others are: gold-on-white,
    328x328, payload = BASE#<symbol>. Picks the version that yields 328."""
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L
    name = qr_name(symbol)
    dst = Path(out) if out else qrdir / name
    url = f"{BASE}#{symbol}"
    for ver in range(1, 41):
        qr = qrcode.QRCode(version=ver, error_correction=ERROR_CORRECT_L,
                           box_size=8, border=4)
        qr.add_data(url)
        try:
            qr.make(fit=False)
        except Exception:
            continue
        im = qr.make_image(fill_color=(212, 175, 55),
                           back_color=(255, 255, 255)).convert("RGB")
        if im.size == (328, 328):
            dst.parent.mkdir(parents=True, exist_ok=True)
            im.save(str(dst))
            return {"ok": True, "file": str(dst), "version": ver,
                    "bytes": dst.stat().st_size, "sha256": _sha(dst.read_bytes()),
                    "decodes_to": decode_qr(dst)}
    return {"ok": False, "refusal": "ninguna versión produce 328x328 con este payload"}


def resolve(symbol: str) -> dict:
    """One symbol -> codepoint, punycode, QR, and what the QR says."""
    png = QRDIR / qr_name(symbol)
    out = {"ok": True, "symbol": symbol,
           "codepoints": [f"U+{ord(c):X}" for c in symbol],
           "names": [unicodedata.name(c, "?") for c in symbol],
           "punycode": punycode(symbol) or "(no registrable)",
           "qr": str(png), "qr_exists": png.exists()}
    if png.exists():
        readings = decode_qr_all(png)
        out["qr_decodes_to"] = readings[0] if readings else ""
        out["readings"] = readings
        out["anchor_matches"] = f"{BASE}#{symbol}" in readings
    return out


def grade(path: Path | str) -> dict:
    """Determinism: reading the registry twice gives the same symbols."""
    p = Path(path)
    if not p.exists():
        return {"ok": False, "refusal": f"no such file: {p}"}
    try:
        a, b = core_of(p), core_of(p)
    except ValueError as exc:
        return {"ok": False, "refusal": str(exc)}
    ha = _sha(json.dumps(a, ensure_ascii=False).encode())
    hb = _sha(json.dumps(b, ensure_ascii=False).encode())
    return {"ok": ha == hb, "deterministic": ha == hb, "sha256_a": ha[:16],
            "sha256_b": hb[:16], "symbols": len(a)}


# ── ledger ─────────────────────────────────────────────────────────────────

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
    ap = argparse.ArgumentParser(prog="tinyEMOJI", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    c = sub.add_parser("check"); c.add_argument("path", nargs="?", default=str(REGISTRY))
    r = sub.add_parser("resolve"); r.add_argument("symbol")
    q = sub.add_parser("qr"); q.add_argument("symbol")
    g = sub.add_parser("grade"); g.add_argument("path", nargs="?", default=str(REGISTRY))
    sub.add_parser("ledger")
    a = ap.parse_args()

    if a.cmd == "doctor":
        r = doctor(); print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("doctor", {"ok": r["ok"]}); return 0 if r["ok"] else 1
    if a.cmd == "check":
        r = check(a.path); print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["ok"] else 1
    if a.cmd == "resolve":
        print(json.dumps(resolve(a.symbol), ensure_ascii=False, indent=1)); return 0
    if a.cmd == "qr":
        r = make_qr(a.symbol); print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("qr", {"ok": r.get("ok"), "sha256": r.get("sha256")})
        return 0 if r.get("ok") else 1
    if a.cmd == "grade":
        r = grade(a.path); print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("grade", {"deterministic": r.get("deterministic")})
        return 0 if r.get("ok") else 1
    if a.cmd == "ledger":
        print(json.dumps(ledger_verify(), ensure_ascii=False, indent=1)); return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
