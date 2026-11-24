#!/usr/bin/env python3
"""tinySURFACE — the sovereign instrument for published surfaces.

tinySURFACE does NOT write pages. It GOVERNS them: it walks a directory of
surfaces and measures the two things the estate requires of every one — a
canonical address and a signed badge ("a surface without a badge is a claim
without a signature"). What is missing is NAMED, never painted over.

    doctor    audit aipodcast_me/: counts, and names every surface that fails
    audit     same, for any directory, machine-readable
    fix       add the missing canonical + badge, sealing each with tinyqr
              (--dry-run by default: it reports, it does not touch)

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
from pathlib import Path

ROOT = Path(r"C:\æ")
PAGE_DIR = ROOT / "github-pages" / "aipodcast_me"
LEDGER = Path(os.environ.get("TINYSURFACE_LEDGER", r"C:\æ\logs\tinysurface.jsonl"))
GENESIS = "0" * 64
BASE = "https://myaelmendez.github.io/aipodcast_me/"

BADGE = ('<a id="ae-qr-badge" href="{name}.html.receipt.json" target="_blank" '
         'rel="noopener" aria-label="Verify this surface" style="{style}">\n'
         '        <img src="{name}.html.receipt.png" alt="QR de la firma tinyqr" '
         'width="64" height="64" style="width:100%;height:100%;display:block;'
         'border-radius:4px">\n      </a>')
STYLE = ("width:64px;height:64px;border:1px solid var(--gold);border-radius:8px;"
         "background:var(--void);padding:4px;display:block;text-decoration:none;"
         "box-shadow:0 8px 30px rgba(0,0,0,.6)")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def audit_dir(d: Path | str) -> dict:
    """Measure every .html in a directory. Reads the artifacts, never names."""
    d = Path(d)
    if not d.is_dir():
        return {"ok": False, "refusal": f"no such directory: {d}"}
    rows = []
    for f in sorted(d.glob("*.html")):
        s = f.read_text(encoding="utf-8", errors="replace")
        badge = "ae-qr-badge" in s
        canon = 'rel="canonical"' in s
        # the badge is only real if its chip exists and its receipt too
        receipt = (d / f"{f.name}.receipt.json").exists()
        qr = (d / f"{f.name}.receipt.png").exists()
        rows.append({"surface": f.name, "bytes": len(s.encode()),
                     "badge": badge, "canonical": canon,
                     "receipt": receipt, "qr": qr})
    both = [r["surface"] for r in rows if r["badge"] and r["canonical"]]
    out = {"ok": True, "directory": str(d), "surfaces": len(rows),
           "con_ambas": len(both),
           "sin_badge": [r["surface"] for r in rows if not r["badge"]],
           "sin_canonical": [r["surface"] for r in rows if not r["canonical"]],
           "sin_receipt": [r["surface"] for r in rows if not r["receipt"]],
           "rows": rows}
    out["ok"] = bool(both)
    return out


def doctor() -> dict:
    a = audit_dir(PAGE_DIR)
    out = {"ok": False, "checks": {
        "surfaces": a.get("surfaces"),
        "con_ambas": a.get("con_ambas"),
        "sin_badge": len(a.get("sin_badge") or []),
        "sin_canonical": len(a.get("sin_canonical") or []),
        "sin_receipt": len(a.get("sin_receipt") or []),
    }}
    if not a.get("ok"):
        out["refusal"] = (f"{out['checks']['sin_badge']} sin badge · "
                          f"{out['checks']['sin_canonical']} sin canonical · "
                          f"{out['checks']['sin_receipt']} sin recibo")
        return out
    out["ok"] = True
    out["note"] = "medido en esta maquina, no asumido"
    return out


# ── fix ────────────────────────────────────────────────────────────────────

def fix_dir(d: Path | str, write: bool = False, key: str = "sovereign-web",
            exclude: tuple[str, ...] = ("index.html",)) -> dict:
    """Add the missing canonical and badge, sealing each with tinyqr.

    Dry-run unless write=True: the instrument REPORTS first, always.
    """
    d = Path(d)
    a = audit_dir(d)
    if not a.get("surfaces"):
        return {"ok": False, "refusal": f"sin superficies en {d}"}
    fixed, skipped, failed = [], [], []
    for row in a["rows"]:
        if any(row["surface"] == e or row["surface"].startswith(e) for e in exclude):
            skipped.append(row["surface"]); continue
        f = d / row["surface"]
        s = f.read_text(encoding="utf-8")
        orig = s
        url = BASE + row["surface"]
        if not row["canonical"]:
            if "<head>" in s:
                s = s.replace("<head>", f'<head>\n<link rel="canonical" href="{url}">', 1)
            elif "<html" in s:
                m = re.search(r"(<html[^>]*>)", s)
                s = s[:m.end()] + f'\n<head><link rel="canonical" href="{url}"></head>' + s[m.end():]
            else:
                failed.append((row["surface"], "sin <head> donde insertar")); continue
        if not row["badge"]:
            block = BADGE.format(name=row["surface"], style=STYLE)
            if "</body>" in s:
                s = s.replace("</body>", f"\n  <footer style=\"display:flex;justify-content:"
                                     f"space-between;align-items:center;gap:14px;flex-wrap:wrap\">\n"
                                     f"    <span>{row['surface']}</span>\n    {block}\n  </footer>\n</body>", 1)
            else:
                failed.append((row["surface"], "sin </body> donde insertar")); continue
        if s == orig:
            skipped.append(row["surface"]); continue
        if write:
            f.write_text(s, encoding="utf-8")
            # seal: the badge links to a real receipt
            try:
                sys.path.insert(0, str(ROOT / "tinyqr"))
                import tinyqr
                r = tinyqr.seal(f, key)
                if not r.get("ok"):
                    failed.append((row["surface"], f"sello: {r.get('refusal')}"))
            except Exception as exc:
                failed.append((row["surface"], f"sello: {type(exc).__name__}: {exc}"))
        fixed.append(row["surface"])
    return {"ok": not failed, "mode": "write" if write else "dry-run",
            "fixed": len(fixed), "skipped": len(skipped), "failed": failed[:12],
            "samples": fixed[:8]}


def grade(d: Path | str) -> dict:
    a = audit_dir(d)
    ha = _sha(json.dumps(a["rows"], ensure_ascii=False).encode())
    b = audit_dir(d)
    hb = _sha(json.dumps(b["rows"], ensure_ascii=False).encode())
    return {"ok": ha == hb, "deterministic": ha == hb, "sha256_a": ha[:16],
            "sha256_b": hb[:16], "surfaces": a.get("surfaces")}


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
    return [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]


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
    ap = argparse.ArgumentParser(prog="tinySURFACE", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    a = sub.add_parser("audit"); a.add_argument("dir", nargs="?", default=str(PAGE_DIR))
    fx = sub.add_parser("fix"); fx.add_argument("dir", nargs="?", default=str(PAGE_DIR))
    fx.add_argument("--write", action="store_true")
    g = sub.add_parser("grade"); g.add_argument("dir", nargs="?", default=str(PAGE_DIR))
    sub.add_parser("ledger")
    arg = ap.parse_args()

    if arg.cmd == "doctor":
        r = doctor(); print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["ok"] else 1
    if arg.cmd == "audit":
        r = audit_dir(arg.dir); print(json.dumps({k: v for k, v in r.items() if k != "rows"},
                                                 ensure_ascii=False, indent=1)); return 0 if r.get("ok") else 1
    if arg.cmd == "fix":
        r = fix_dir(arg.dir, write=arg.write)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("fix", {"fixed": r.get("fixed"), "failed": len(r.get("failed") or [])})
        return 0 if r.get("ok") else 1
    if arg.cmd == "grade":
        r = grade(arg.dir); print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("grade", {"deterministic": r.get("deterministic")}); return 0 if r["ok"] else 1
    if arg.cmd == "ledger":
        print(json.dumps(ledger_verify(), ensure_ascii=False, indent=1)); return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
