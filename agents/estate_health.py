#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""æ:// estate health — does every surface exist, and does what it cites exist?

The estate rule is "a number is either read from a live source or labelled
unverified". This is the instrument for the first half of that: it asks of all
418 surfaces whether the page resolves and whether the artifacts it cites
resolve. No opinions, no thresholds — two booleans per surface, receipted.

    python agents/estate_health.py            # writes estate-health.json
    python agents/estate_health.py --quiet    # summary only

Checks, per surface:
  page      the URL returns 200
  cites     every relative asset the page names (src/href/url/fetch) exists
            on disk, resolved against the page's own directory
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("C:/æ")
PAGES = ROOT / "github-pages"
ESTATE = PAGES / "estate.json"
OUT = PAGES / "estate-health.json"
BASE = "https://myaelmendez.github.io/"

REF = re.compile(
    r"""(?:src|href)\s*=\s*["']([^"']+)["']"""
    r"""|url\(\s*["']?([^"')]+)["']?\s*\)"""
    r"""|fetch\(\s*["']([^"']+)["']""",
    re.I,
)
SKIP = re.compile(r"^(https?:|//|data:|mailto:|#|javascript:)", re.I)


def local_refs(text: str, page: Path) -> list[str]:
    """Relative paths the page names, resolved against the page's directory."""
    out = []
    for m in REF.finditer(text):
        raw = next(g for g in m.groups() if g)
        if SKIP.match(raw):
            continue
        # a JS expression, not a path: template placeholders, concatenation,
        # identifiers. A real asset path has none of these, and its basename
        # carries an extension on a stem of at least two characters.
        if re.search(r"[$+{}\s'\"]", raw):
            continue
        base = raw.rstrip("/").rsplit("/", 1)[-1]
        if not re.match(r"^.{2,}\.[A-Za-z0-9]{1,6}$", base):
            continue
        raw = raw.split("?")[0].split("#")[0]
        if not raw:
            continue
        p = (page.parent / raw).resolve() if not raw.startswith("/") else PAGES / raw.lstrip("/")
        try:
            p.relative_to(PAGES.resolve())
        except ValueError:
            continue
        out.append(p)
    return sorted(set(out))


def check_page(item: dict) -> dict:
    url = item["url"]
    path = PAGES / url.lstrip("/")
    rec = {"url": url, "path": str(path), "title": item.get("title", "")}

    try:
        from urllib.parse import quote
        target = BASE + quote(url.lstrip("/"), safe="/:")
        req = urllib.request.Request(target, method="GET",
                                     headers={"User-Agent": "ae-estate-health/1"})
        with urllib.request.urlopen(req, timeout=25) as r:
            rec["page"] = 200 <= r.status < 400
            rec["status"] = r.status
    except Exception as e:
        rec["page"] = False
        rec["status"] = getattr(e, "code", type(e).__name__)

    refs = local_refs(path.read_text(encoding="utf-8", errors="replace"), path) if path.exists() else []
    missing = [str(p) for p in refs if not p.exists()]
    rec["cites"] = len(refs)
    rec["missing"] = missing
    rec["ok"] = bool(rec["page"]) and not missing
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--workers", default=24, type=int)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    estate = json.loads(ESTATE.read_text(encoding="utf-8"))
    surfaces = estate["surfaces"]
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        rows = list(ex.map(check_page, surfaces))

    dead = [r for r in rows if not r["page"]]
    dangling = [r for r in rows if r["missing"]]
    ok = [r for r in rows if r["ok"]]
    doc = {
        "schema": "æ-estate-health/1",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "authority": "HUMAN://ROOT",
        "source": "agents/estate_health.py",
        "base": BASE,
        "counts": {
            "surfaces": len(rows),
            "reachable": len(rows) - len(dead),
            "unreachable": len(dead),
            "with_dangling_refs": len(dangling),
            "healthy": len(ok),
        },
        "unreachable": [{"url": r["url"], "status": r["status"]} for r in dead],
        "dangling": [{"url": r["url"], "missing": r["missing"]} for r in dangling],
        "rows": rows,
    }
    Path(a.out).write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    c = doc["counts"]
    print(f"wrote {a.out}")
    print(f"  surfaces {c['surfaces']}  reachable {c['reachable']}  "
          f"unreachable {c['unreachable']}  dangling {c['with_dangling_refs']}  healthy {c['healthy']}")
    for r in dead[:12]:
        print(f"  DEAD {r['url']}  ({r['status']})")
    for r in dangling[:12]:
        print(f"  DANGLING {r['url']}  -> {r['missing'][:3]}")
    if a.quiet:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
