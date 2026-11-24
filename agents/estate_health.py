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
BASE_TAG = re.compile(r"<base\b[^>]*?href\s*=\s*[\"']([^\"']+)[\"']", re.I)


def page_root(text: str, page: Path) -> Path:
    """The directory a relative reference resolves from.

    A page may declare <base href="..">, which every relative URL in it obeys.
    Ignoring it makes a correct page read as dangling — exactly the defect this
    instrument exists to catch, so honour it before judging anything.
    """
    m = BASE_TAG.search(text)
    if not m:
        return page.parent
    raw = m.group(1).strip().split("?")[0].split("#")[0]
    if not raw or SKIP.match(raw):
        return page.parent
    if raw.startswith("/"):
        return (PAGES / raw.lstrip("/")).resolve()
    return (page.parent / raw).resolve()


def local_refs(text: str, page: Path) -> list[str]:
    """Relative paths the page names, resolved against its own base."""
    out = []
    root = page_root(text, page)
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
        p = (root / raw).resolve() if not raw.startswith("/") else (PAGES / raw.lstrip("/")).resolve()
        try:
            p.relative_to(PAGES.resolve())
        except ValueError:
            continue
        out.append(p)
    return sorted(set(out))


def declared_unbuilt() -> set[str]:
    """Artifacts a surface cites but that are deliberately not built yet.

    `unbuilt.txt` is the honest alternative to deleting a reference: the count of
    dangling refs then means "every reference resolves or is named here", and the
    unbuilt list stays published rather than hidden behind a 404.
    """
    out = set()
    f = PAGES / "unbuilt.txt"
    if not f.exists():
        return out
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        first = line.split("|")[0].strip().replace("/", "\\")
        if first:
            out.add(str((PAGES / first).resolve()))
    return out


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
    UNBUILT = declared_unbuilt()
    dangling = [m for m in missing if m not in UNBUILT]
    rec["cites"] = len(refs)
    rec["missing"] = dangling
    rec["unbuilt"] = sorted(m for m in missing if m in UNBUILT)
    rec["ok"] = bool(rec["page"]) and not dangling
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

    # A page that 404s may be someone's unpublished draft, not a broken estate.
    # Say which, so "0 unreachable" is never achieved by hiding work.
    tracked = set()
    try:
        import subprocess
        out = subprocess.run(["git", "-C", str(PAGES), "ls-files"],
                             capture_output=True, text=True)
        if out.returncode == 0:
            tracked = {str((PAGES / ln.strip()).resolve()) for ln in out.stdout.splitlines() if ln.strip()}
    except Exception:
        tracked = set()
    untracked = []
    for r in dead:
        r["tracked"] = Path(r["path"]).resolve() in tracked
        if r["tracked"]:
            r["state"] = "published-404"
        elif Path(r["path"]).exists():
            r["state"] = "untracked-draft"
            untracked.append(r)
        else:
            r["state"] = "missing-file"

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
            "published_404": sum(1 for r in dead if r.get("state") == "published-404"),
            "untracked_drafts": len(untracked),
            "missing_files": sum(1 for r in dead if r.get("state") == "missing-file"),
            "with_dangling_refs": len(dangling),
            "declared_unbuilt": sum(len(r.get("unbuilt", [])) for r in rows),
            "healthy": len(ok),
        },
        "unreachable": [{"url": r["url"], "status": r["status"], "state": r.get("state"),
                         "tracked": r.get("tracked")} for r in dead],
        "dangling": [{"url": r["url"], "missing": r["missing"]} for r in dangling],
        "unbuilt": [{"url": r["url"], "artifacts": r["unbuilt"]}
                    for r in rows if r.get("unbuilt")],
        "rows": rows,
    }
    Path(a.out).write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    c = doc["counts"]
    print(f"wrote {a.out}")
    print(f"  surfaces {c['surfaces']}  reachable {c['reachable']}  "
          f"unreachable {c['unreachable']}  dangling {c['with_dangling_refs']}  "
          f"declared_unbuilt {c['declared_unbuilt']}  healthy {c['healthy']}")
    print(f"  unreachable breakdown: published-404 {c['published_404']} · "
          f"untracked drafts {c['untracked_drafts']} · missing files {c['missing_files']}")
    for r in dead[:12]:
        print(f"  {r.get('state','?').upper()} {r['url']}  ({r['status']})"
              f"  tracked={r.get('tracked')}")
    for r in dangling[:12]:
        print(f"  DANGLING {r['url']}  -> {r['missing'][:3]}")
    if a.quiet:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
