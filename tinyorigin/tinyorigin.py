#!/usr/bin/env python3
"""tinyORIGIN — the origin atlas as an instrument, not a page.

The origin surface (github.io/origin) renders the x:y:z:æ atlas and its terminal
prints status strings that are HISTORICAL DEMO TEXT — the page does not verify
them. tinyORIGIN is the instrument that does:

    atlas      the address index: count + categories, from ae-atlas.json
    resolve    coordinate + url for an address/name, and the MEASURED http status
    verify     walk every address; liveness + a sha256 receipt of the whole sweep
    receipt    the ledger, hash-chained
    drift      compare the live index against the surface's fallback feed

One file, stdlib, deterministic. Simulation of nothing: it measures URLs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ATLAS = ROOT / "github-pages" / "ae-atlas.json"
ORIGIN_HTML = ROOT / "github-pages" / "origin" / "index.html"
LEDGER = ROOT / "logs" / "origin" / "tinyorigin.jsonl"
TIMEOUT = float(os.environ.get("TINYORIGIN_TIMEOUT", "12"))


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _last_hash() -> str:
    if LEDGER.exists():
        lines = [l for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            try:
                return json.loads(lines[-1])["hash"]
            except Exception:
                pass
    return "0" * 64


def receipt(action: str, detail: dict) -> dict:
    body = {"ts": stamp(), "action": action, "detail": detail, "prev": _last_hash()}
    body["hash"] = hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(canonical(body) + "\n")
    return body


def load_atlas() -> dict:
    return json.loads(ATLAS.read_text(encoding="utf-8"))


def coord_of(a: dict) -> str:
    return f"x{a.get('x')}:y{a.get('y')}:z{a.get('z')}:æ{a.get('a')}"


BASE = os.environ.get("TINYORIGIN_BASE", "https://myaelmendez.github.io")


def http_status(url: str) -> dict:
    """Measure the URL. Never assert it. Root-relative atlas urls resolve on BASE."""
    if not url:
        return {"url": "", "status": None, "reason": "no url"}
    full = BASE + url if url.startswith("/") else url
    try:
        req = urllib.request.Request(full, method="HEAD", headers={"User-Agent": "tinyorigin/1"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return {"url": full, "status": r.status, "reason": "ok"}
    except urllib.error.HTTPError as e:
        return {"url": full, "status": e.code, "reason": "http"}
    except Exception as e:
        return {"url": full, "status": None, "reason": f"{type(e).__name__}: {e}"[:120]}


def cmd_atlas(_a) -> int:
    d = load_atlas()
    cats = [c.get("name") if isinstance(c, dict) else c for c in d.get("categories", [])]
    print(json.dumps({"schema": "tinyorigin.atlas.v1", "source": str(ATLAS),
                      "count_field": d.get("count"), "addresses": len(d["addresses"]),
                      "categories": cats}, indent=1, ensure_ascii=False))
    receipt("atlas", {"addresses": len(d["addresses"]), "count_field": d.get("count")})
    return 0


def cmd_resolve(a) -> int:
    d = load_atlas()
    q = a.query
    hit = None
    for addr in d["addresses"]:
        if q in (addr.get("id"), coord_of(addr), addr.get("name")):
            hit = addr
            break
    if hit is None:
        ql = q.lower()
        for addr in d["addresses"]:
            blob = " ".join(str(addr.get(k, "")) for k in ("id", "name", "url", "cat"))
            if ql in blob.lower():
                hit = addr
                break
    if hit is None:
        print(json.dumps({"found": False, "query": q}))
        return 2
    r = http_status(hit.get("url", ""))
    out = {"found": True, "query": q, "id": hit.get("id"), "name": hit.get("name"),
           "coordinate": coord_of(hit), "layer": hit.get("layer"),
           "category": hit.get("cat") or hit.get("category"), **r}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    receipt("resolve", {"id": hit.get("id"), "coordinate": coord_of(hit), "status": r["status"]})
    return 0 if r["status"] == 200 else 1


def cmd_verify(a) -> int:
    d = load_atlas()
    rows, live, dead = [], 0, 0
    for addr in d["addresses"]:
        r = http_status(addr.get("url", ""))
        ok = r["status"] == 200
        live += 1 if ok else 0
        dead += 0 if ok else 1
        rows.append({"coordinate": coord_of(addr), "id": addr.get("id"),
                     "status": r["status"], "reason": r["reason"]})
    rec = receipt("verify", {"addresses": len(rows), "live": live, "dead": dead})
    print(json.dumps({"schema": "tinyorigin.verify.v1", "addresses": len(rows),
                      "live": live, "dead": dead, "receipt": rec["hash"],
                      "rows": rows if a.full else rows[:8]}, indent=1, ensure_ascii=False))
    return 0


def cmd_drift(_a) -> int:
    """Compare the two atlas artifacts and the index against the live surface."""
    d = load_atlas()
    live = len(d["addresses"])
    js = ROOT / "github-pages" / "ae-atlas.js"
    js_ids, js_n = [], None
    if js.exists():
        import re
        t = js.read_text(encoding="utf-8", errors="replace")
        js_ids = re.findall(r'"id"\s*:\s*"([^"]+)"', t)
        js_n = len(js_ids)
    json_ids = {a.get("id") for a in d["addresses"]}
    out = {"schema": "tinyorigin.drift.v1",
           "ae_atlas_json": live,
           "ae_atlas_js": js_n,
           "mesh_vs_feed_drift": (js_n is not None and js_n != live),
           "only_in_js": sorted(set(js_ids) - json_ids),
           "only_in_json": sorted(json_ids - set(js_ids))}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    receipt("drift", {k: v for k, v in out.items() if k != "schema"})
    return 0


def cmd_receipt(a) -> int:
    if not LEDGER.exists():
        print("no ledger.")
        return 0
    lines = [l for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
    for l in lines[-a.n:]:
        print(l)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tinyORIGIN")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("atlas").set_defaults(fn=cmd_atlas)
    r = sub.add_parser("resolve")
    r.add_argument("query")
    r.set_defaults(fn=cmd_resolve)
    v = sub.add_parser("verify")
    v.add_argument("--full", action="store_true")
    v.set_defaults(fn=cmd_verify)
    sub.add_parser("drift").set_defaults(fn=cmd_drift)
    rc = sub.add_parser("receipt")
    rc.add_argument("n", nargs="?", type=int, default=10)
    rc.set_defaults(fn=cmd_receipt)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
