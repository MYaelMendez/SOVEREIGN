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


def cmd_opportunity(_a) -> int:
    """The atlas as an instrument: what the estate has not addressed, ranked by weight.

    Reads estate.json (generated from the repository) and the live status of every
    addressed surface. Nothing here is typed.
    """
    from collections import Counter
    est = ROOT / "github-pages" / "estate.json"
    if not est.exists():
        print(json.dumps({"schema": "tinyorigin.opportunity.v1",
                          "error": "estate.json missing"}))
        return 1
    e = json.loads(est.read_text(encoding="utf-8"))
    s = e.get("surfaces", [])
    at = [x for x in s if x.get("atlas")]
    un = [x for x in s if not x.get("atlas")]
    total_b = sum(x.get("bytes", 0) for x in s)
    un_b = sum(x.get("bytes", 0) for x in un)
    cnt = Counter(x.get("bytes", 0) for x in un)
    dupes = [{"bytes": b, "copies": n, "waste": b * (n - 1)}
             for b, n in cnt.items() if n > 1 and b > 0]
    dupes.sort(key=lambda d: -d["waste"])
    dead = []
    for x in at:
        url = x.get("url")
        if not url:
            continue
        st = http_status(url)
        if st.get("status") != 200:
            dead.append({"id": x.get("id"), "coord": x.get("coord"),
                         "status": st.get("status")})
    out = {"schema": "tinyorigin.opportunity.v1",
           "generated": e.get("generated"),
           "surfaces": len(s), "addressed": len(at), "unaddressed": len(un),
           "bytes_total": total_b, "bytes_unaddressed": un_b,
           "unaddressed_share": round(un_b / total_b, 4) if total_b else 0,
           "vertical_unaddressed": sum(1 for x in un if x.get("vertical")),
           "films_unaddressed": sum(1 for x in un if x.get("film")),
           "duplicate_groups": len(dupes),
           "duplicate_waste_bytes": sum(d["waste"] for d in dupes),
           "top_duplicates": dupes[:5],
           "top_unaddressed": [{"bytes": x.get("bytes"), "url": x.get("url")}
                               for x in sorted(un, key=lambda y: -y.get("bytes", 0))[:5]],
           "dead_addresses": dead}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    receipt("opportunity", {k: v for k, v in out.items()
                            if k not in ("schema", "top_unaddressed",
                                         "top_duplicates", "dead_addresses")})
    return 0


def cmd_gems(_a) -> int:
    """Mine the atlas for gems: unaddressed surfaces that rank high on SEVERAL independent
    signals at once. No single magic score — each signal is computed and ranked, and a gem
    is a surface near the top of more than one ranking (a consensus you can audit).

    Signals, all measured from the files:
      inbound   other surfaces that reference this one's url
      evidence  sha256 strings and PASS/RECEIPT/gate words inside it (receipts, gates)
      code      bytes of text it actually contains (a proxy for authored effort)
    """
    import re
    est = ROOT / "github-pages" / "estate.json"
    if not est.exists():
        print(json.dumps({"schema": "tinyorigin.gems.v1", "error": "estate.json missing"}))
        return 1
    e = json.loads(est.read_text(encoding="utf-8"))
    s = e.get("surfaces", [])
    base = ROOT / "github-pages"
    texts = {}
    for x in s:
        p = base / (x.get("url") or "").lstrip("/")
        if p.is_file():
            try:
                texts[x.get("id")] = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                texts[x.get("id")] = ""
    rec = re.compile(r"\b[0-9a-f]{64}\b")
    gate = re.compile(r"(?i)\b(PASS|RECEIPT|GATE)\b")
    un = [x for x in s if not x.get("atlas")]
    for x in un:
        t = texts.get(x.get("id"), "")
        x["_in"] = 0
        x["_sha"] = len(rec.findall(t))
        x["_gate"] = len(gate.findall(t))
        x["_chars"] = len(t)
    for x in un:
        needle = (x.get("url") or "").lstrip("/")
        if len(needle) < 6:          # a short path is a substring of half the estate
            continue
        x["_in"] = sum(1 for k, t in texts.items()
                       if k != x.get("id") and needle in t)
    # one entry per path: several surfaces share an id across directories
    seen, uniq = set(), []
    for x in un:
        u = x.get("url") or x.get("id")
        if u in seen:
            continue
        seen.add(u)
        uniq.append(x)
    un = uniq
    top = lambda key, n=10: [
        {"id": x.get("id"), "url": x.get("url"), "bytes": x.get("bytes"),
         "inbound": x["_in"], "sha": x["_sha"], "gate": x["_gate"]}
        for x in sorted(un, key=lambda y: -y[key])[:n]]
    ranks = {"demand": top("_in"), "evidence": top("_sha"),
             "gate": top("_gate"), "size": top("_chars")}
    tally = {}
    for name, rows in ranks.items():
        for r in rows:
            t = tally.setdefault(r["url"], {"id": r["id"], "url": r["url"],
                                            "bytes": r["bytes"], "signals": []})
            t["signals"].append(name)
    consensus = sorted(tally.values(), key=lambda t: (-len(t["signals"]), -t["bytes"]))[:12]
    out = {"schema": "tinyorigin.gems.v1", "generated": e.get("generated"),
           "unaddressed": len(un), "rankings": ranks, "consensus": consensus}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    receipt("gems", {"unaddressed": len(un),
                     "consensus": [c["id"] for c in consensus]})
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
    sub.add_parser("opportunity").set_defaults(fn=cmd_opportunity)
    sub.add_parser("gems").set_defaults(fn=cmd_gems)
    rc = sub.add_parser("receipt")
    rc.add_argument("n", nargs="?", type=int, default=10)
    rc.set_defaults(fn=cmd_receipt)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
