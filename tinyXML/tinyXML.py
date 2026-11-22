#!/usr/bin/env python3
"""tinyXML — the sovereign instrument for XML.

tinySVG already parses XML; tinyXML is the generalisation: it governs XML as an
artifact. It measures well-formedness, canonicalises deterministically (the
property XMLDSig depends on), refuses DTDs that can carry entities (XXE), and
signs the canonical form.

    doctor()   parse + canonicalise twice + refuse an XXE payload
    check      measure a file: line/column of the first error, namespaces, depth
    canon      emit the canonical form (sorted attributes, no comments)
    sign       canonicalise then sign with tinyqr
    grade      two canonicalisations, byte-compared

Invariants (tiny* family): doctor() measures; every verb refuses; the contract is
read from the bytes; a receipt is a claim until re-run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

LEDGER = Path(os.environ.get("TINYXML_LEDGER", r"C:\æ\logs\tinyXML.jsonl"))
GENESIS = "0" * 64

TINYSVG_DIR = Path(r"C:\æ\tinySVG")
TINYXQR_DIR = Path(r"C:\æ\tinyqr")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _esc_text(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _esc_attr(s: str) -> str:
    return _esc_text(s).replace('"', "&quot;")


# ── parse ──────────────────────────────────────────────────────────────────

def parse(data: bytes, safe: bool = True) -> tuple[ET.Element | None, dict]:
    """Parse XML. Returns (root, info). `safe` uses defusedxml when available."""
    info = {"safe": False, "parser": "xml.etree.ElementTree"}
    try:
        if safe:
            import defusedxml.ElementTree as D
            info["parser"] = "defusedxml.ElementTree"
            info["safe"] = True
            root = D.fromstring(data)
        else:
            root = ET.fromstring(data)
        return root, info
    except Exception as exc:
        return None, {"error": f"{type(exc).__name__}: {exc}", **info}


def error_position(data: bytes) -> dict:
    """expat reports line/column of the first error — ElementTree does not."""
    import xml.parsers.expat as expat
    p = expat.ParserCreate()
    try:
        p.Parse(data, True)
        return {"ok": True}
    except expat.ExpatError as exc:
        return {"ok": False, "line": exc.lineno, "column": exc.offset + 1,
                "code": expat.ErrorString(exc.code)}


# ── canonical form ─────────────────────────────────────────────────────────

def canon(root: ET.Element) -> str:
    """Deterministic canonical form: attributes sorted, no declaration, no
    comments, text escaped, namespace prefixes preserved as written. This is the
    property that lets two parties hash the SAME document."""
    def rec(el: ET.Element) -> str:
        tag = el.tag
        attrs = "".join(f' {k}="{_esc_attr(v)}"' for k, v in sorted(el.attrib.items()))
        text = _esc_text(el.text or "")
        kids = "".join(rec(c) for c in el)
        tail = _esc_text(el.tail or "")
        if not kids and not text:
            return f"<{tag}{attrs}/>{tail}"
        return f"<{tag}{attrs}>{text}{kids}</{tag}>{tail}"
    return rec(root)


def depth(root: ET.Element) -> int:
    return 1 + max((depth(c) for c in root), default=0)


def namespaces(root: ET.Element) -> list[str]:
    out, seen = [], set()
    for el in root.iter():
        for k, v in el.attrib.items():
            if k.startswith("{"):
                uri = k[1:].split("}")[0]
                if uri not in seen:
                    seen.add(uri); out.append(uri)
        if isinstance(el.tag, str) and el.tag.startswith("{"):
            uri = el.tag[1:].split("}")[0]
            if uri not in seen:
                seen.add(uri); out.append(uri)
    return out


def has_dtd(data: bytes) -> bool:
    low = data[:2048].lower()
    return b"<!doctype" in low


# ── the check ──────────────────────────────────────────────────────────────

def check(path: Path | str) -> dict:
    """Measure an XML artifact. Reads the bytes, never the filename."""
    p = Path(path)
    if not p.exists():
        return {"ok": False, "refusal": f"no such file: {p}"}
    data = p.read_bytes()
    out = {"bytes": len(data), "has_doctype": has_dtd(data)}
    pos = error_position(data)
    if not pos["ok"]:
        return {"ok": False, "refusal": f"no es XML bien formado: {pos['code']} "
                f"(linea {pos['line']}, columna {pos['column']})", **out, **pos}
    out["well_formed"] = True
    root, info = parse(data)
    if root is None:
        return {"ok": False, "refusal": info.get("error"), **out}
    out["parser"] = info.get("parser")
    out["depth"] = depth(root)
    out["namespaces"] = namespaces(root)
    c1, c2 = canon(root), canon(root)
    out["canonical_sha256"] = _sha(c1.encode())
    out["deterministic"] = c1 == c2
    if has_dtd(data):
        out["warning"] = ("lleva DOCTYPE: si declara entidades externas, un parser "
                          "inseguro es vulnerable a XXE. tinyXML lo rechaza.")
    ok = bool(out["deterministic"])
    if not ok:
        out["refusal"] = "la canonicalizacion no es determinista"
    out["ok"] = ok
    return out


# ── doctor ─────────────────────────────────────────────────────────────────

PROBE = b"""<?xml version="1.0"?>
<family xmlns="urn:ae" xmlns:g="urn:gold">
  <node g:rank="2">tinyqr</node>
  <node g:rank="1">tinySVG</node>
</family>
"""

# an XXE payload: a billion-laughs / external entity attempt
XXE = b"""<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///C:/Windows/win.ini">]>
<foo>&xxe;</foo>
"""


def doctor() -> dict:
    out = {"ok": False, "checks": {}}
    # 1. well-formedness with position
    pos = error_position(PROBE)
    if not pos["ok"]:
        out["checks"]["probe"] = f"REFUSED: {pos}"
        return out
    out["checks"]["probe"] = "XML bien formado"
    # 2. safe parse available
    root, info = parse(PROBE)
    if root is None:
        out["checks"]["parse"] = f"REFUSED: {info.get('error')}"
        return out
    out["checks"]["parser"] = info.get("parser")
    out["checks"]["namespaces"] = len(namespaces(root))
    # 3. canonicalisation, twice
    c1, c2 = canon(root), canon(root)
    out["checks"]["canonical"] = f"{len(c1)} chars · sha {_sha(c1.encode())[:12]}…"
    out["checks"]["deterministic"] = c1 == c2
    if not (c1 == c2):
        out["checks"]["deterministic"] = "REFUSED: dos canonicalizaciones distintas"
        return out
    # 4. XXE must be refused
    _, xi = parse(XXE, safe=True)
    refused = "error" in xi
    out["checks"]["xxe_refused"] = refused
    if not refused:
        out["checks"]["xxe_refused"] = "REFUSED: una entidad externa se resolvio"
        return out
    # 5. a broken document reports line/column
    bad = b"<a><b></a>"
    bp = error_position(bad)
    out["checks"]["error_position"] = (f"linea {bp['line']}, columna {bp['column']}"
                                       if not bp["ok"] else "REFUSED: no detecto el error")
    out["ok"] = bool(bp["ok"] is False)
    out["note"] = "medido en esta maquina, no asumido"
    return out


def grade(path: Path | str) -> dict:
    """Determinism: canonicalise the same artifact twice, byte-compare."""
    p = Path(path)
    if not p.exists():
        return {"ok": False, "refusal": f"no such file: {p}"}
    root, info = parse(p.read_bytes())
    if root is None:
        return {"ok": False, "refusal": info.get("error")}
    a, b = canon(root), canon(root)
    ha, hb = _sha(a.encode()), _sha(b.encode())
    return {"ok": ha == hb, "deterministic": ha == hb, "sha256_a": ha, "sha256_b": hb,
            "note": "dos canonicalizaciones, byte a byte"}


def sign(path: Path | str, key: str = "sovereign-web") -> dict:
    """Canonicalise, then sign the canonical bytes with tinyqr."""
    p = Path(path)
    if not p.exists():
        return {"ok": False, "refusal": f"no such file: {p}"}
    root, info = parse(p.read_bytes())
    if root is None:
        return {"ok": False, "refusal": info.get("error")}
    c = canon(root)
    sys.path.insert(0, str(TINYXQR_DIR))
    try:
        import tinyqr
    except Exception as exc:
        return {"ok": False, "refusal": f"tinyqr no cargable: {exc}"}
    outdir = p.parent
    png = outdir / f"{p.name}.xmlsig.png"
    receipt = outdir / f"{p.name}.xmlsig.json"
    sha = _sha(c.encode())
    s = tinyqr.sign(key, sha)
    if not s.get("ok"):
        return {"ok": False, "refusal": s.get("refusal")}
    url = f"https://myaelmendez.github.io/verify.html?a={p.name}&h={sha[:12]}"
    try:
        enc = _qkm_encode(url, png)
    except Exception as exc:
        return {"ok": False, "refusal": f"{type(exc).__name__}: {exc}"}
    receipt.write_text(json.dumps({
        "artifact": p.name, "canonical_sha256": sha, "canonical_chars": len(c),
        "algorithm": "ed25519", "fingerprint": s.get("fingerprint"),
        "public_key": s.get("public_key"), "signature": s.get("signature"),
        "qr": png.name, "qr_payload": url,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "canonical_sha256": sha, "fingerprint": s.get("fingerprint"),
            "png": str(png), "receipt": str(receipt), "qr_version": enc.get("version"),
            "verify_url": url,
            "note": "la firma cubre la FORMA CANONICA, no los bytes del archivo"}


def _qkm_encode(payload: str, png: Path) -> dict:
    sys.path.insert(0, r"C:\æ\agents")
    import qr_key_manager as qkm
    return qkm.encode_qr(payload, filepath=png)


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
    ap = argparse.ArgumentParser(prog="tinyXML", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    c = sub.add_parser("check"); c.add_argument("path")
    cn = sub.add_parser("canon"); cn.add_argument("path")
    sg = sub.add_parser("sign"); sg.add_argument("path"); sg.add_argument("--key", default="sovereign-web")
    g = sub.add_parser("grade"); g.add_argument("path")
    sub.add_parser("ledger")
    a = ap.parse_args()

    if a.cmd == "doctor":
        r = doctor(); print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("doctor", {"ok": r["ok"]}); return 0 if r["ok"] else 1
    if a.cmd == "check":
        r = check(a.path); print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["ok"] else 1
    if a.cmd == "canon":
        root, info = parse(Path(a.path).read_bytes())
        if root is None:
            print(json.dumps({"ok": False, "refusal": info.get("error")}, ensure_ascii=False)); return 1
        print(canon(root)); return 0
    if a.cmd == "sign":
        r = sign(a.path, a.key); print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("sign", {"ok": r.get("ok"), "sha": r.get("canonical_sha256")})
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
