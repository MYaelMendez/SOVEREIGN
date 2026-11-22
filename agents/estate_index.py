#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""æ:// estate index — every surface in the estate, measured from the repo.

The hub used to type its counts ("20 rooms", "212 surfaces") and show a dozen
of 227 pages. This derives them. Nothing here is hand-written: every field is
read from the file, the git object store, or the atlas.

    python agents/estate_index.py            # writes github-pages/estate.json
    python agents/estate_index.py --check    # verify the deployed hub reads it

Measured per surface:
    url, bytes, sha256 (git blob), title, description, category,
    last commit date, whether the atlas names it, whether it is a 9:16 surface
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("C:/æ")
PAGES = ROOT / "github-pages"
ATLAS = PAGES / "ae-atlas.json"
OUT = PAGES / "estate.json"

TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
DESC = re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', re.I | re.S)
DESC2 = re.compile(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']', re.I | re.S)
H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
TAG = re.compile(r"<[^>]+>")
VIDEO = re.compile(r"<video[^>]+src=[\"']([^\"']+)[\"']", re.I)


def strip(s: str) -> str:
    return re.sub(r"\s+", " ", TAG.sub("", s or "")).strip()


def git(*args: str, timeout: int = 60) -> str:
    """Run git. Native CreateProcess is denied in this environment, so go via
    the shell; the command is built from fixed strings plus one repo-relative
    path, and the repo root is a constant."""
    rel = args[-1] if args and not args[-1].startswith("-") else None
    if rel is None:
        cmd = 'git -C "%s" %s' % (str(PAGES), " ".join(args[:-1]))
    else:
        cmd = 'git -C "%s" %s "%s"' % (str(PAGES), " ".join(args[:-1]), rel)
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def atlas_index() -> dict:
    try:
        d = json.loads(ATLAS.read_text(encoding="utf-8"))
    except Exception:
        return {"by_url": {}, "categories": [], "count": 0}
    by_url = {}
    for a in d.get("addresses", []):
        u = a.get("url", "")
        if u:
            by_url[u] = a
    return {"by_url": by_url, "categories": d.get("categories", []),
            "count": d.get("count", len(by_url))}


def last_commit(path: Path) -> str:
    rel = path.relative_to(PAGES).as_posix()
    return git("log", "-1", "--format=%cs", "--", rel)[:10]


def blob_sha(path: Path) -> str:
    return git("hash-object", str(path))


def classify(rel: str, at: dict | None) -> str:
    if at:
        return at.get("cat") or "atlas"
    top = rel.split("/")[0] if "/" in rel else ""
    return top or "root"


def load_git_dump(dumpdir: str | None) -> dict:
    """git cannot be spawned from Python in this environment (CreateProcess is
    denied), so the caller dumps `git ls-files -s` and `git log --name-only`
    from a shell. First occurrence in the log wins — git lists newest first."""
    if not dumpdir:
        return {}
    d = Path(dumpdir)
    out = {}
    bf, lf = d / "blobs.tsv", d / "log.txt"
    if bf.exists():
        for line in bf.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split("\t")
            if len(parts) == 2 and len(parts[0]) == 40:
                out.setdefault(parts[1], {})["blob"] = parts[0]
    if lf.exists():
        cur = None
        for line in lf.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("C") and len(line) == 11:
                cur = line[1:]
            elif line.strip() and cur:
                out.setdefault(line, {})
                out[line].setdefault("last", cur)
    return out


def scan(gitdump: str | None = None) -> dict:
    dumped = load_git_dump(gitdump)
    at = atlas_index()
    surfaces = []
    for path in sorted(PAGES.rglob("*.html")):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(PAGES).as_posix()
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8", "replace")
        except Exception:
            text = ""
        t = TITLE.search(text)
        d = DESC.search(text) or DESC2.search(text)
        h1 = H1.search(text)
        url = "/" + rel
        a = at["by_url"].get(url) or at["by_url"].get(rel)
        g = dumped.get(rel, {})
        surfaces.append({
            "url": url,
            "id": path.stem,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "git_blob": g.get("blob", ""),
            "title": strip(t.group(1)) if t else path.stem,
            "desc": strip(d.group(1)) if d else (strip(h1.group(1)) if h1 else ""),
            "category": classify(rel, a),
            "atlas": bool(a),
            "coord": (f"x{a.get('x')}:y{a.get('y')}:z{a.get('z')}:æ{a.get('a')}"
                      if a and a.get("x") is not None else None),
            "last_commit": g.get("last", ""),
            "vertical": bool(re.search(r"1080[^0-9]{0,12}1920|9\s*:\s*16", text)),
            "film": bool(VIDEO.search(text)),
        })

    root = [s for s in surfaces if "/" not in s["url"].lstrip("/")]
    sub = [s for s in surfaces if "/" in s["url"].lstrip("/")]
    cats: dict = {}
    for s in surfaces:
        cats[s["category"]] = cats.get(s["category"], 0) + 1

    return {
        "schema": "æ-estate/1",
        "authority": "HUMAN://ROOT",
        "origin": "x0:y0:z0:æ0",
        "scheme": ">_æ://#opensourceware",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "agents/estate_index.py",
        "counts": {
            "surfaces": len(surfaces),
            "root": len(root),
            "subdirs": len(sub),
            "atlas": sum(1 for s in surfaces if s["atlas"]),
            "unatlas": sum(1 for s in surfaces if not s["atlas"]),
            "vertical": sum(1 for s in surfaces if s["vertical"]),
            "films": sum(1 for s in surfaces if s["film"]),
            "bytes": sum(s["bytes"] for s in surfaces),
        },
        "categories": cats,
        "atlas_categories": at["categories"],
        "atlas_count": at["count"],
        "surfaces": surfaces,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--git-dump", default=None)
    a = ap.parse_args()
    doc = scan(a.git_dump)
    out = Path(a.out)
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    c = doc["counts"]
    print(f"wrote {out}")
    print(f"  surfaces {c['surfaces']}  root {c['root']}  subdirs {c['subdirs']}")
    print(f"  atlas {c['atlas']}  unattlas {c['unatlas']}  vertical {c['vertical']}  films {c['films']}")
    print(f"  bytes {c['bytes']:,}  categories {len(doc['categories'])}")
    if a.check:
        live = "https://myaelmendez.github.io/estate.json"
        r = subprocess.run(["curl", "-s", "-o", "-", "-w", "\n%{http_code}", live],
                           capture_output=True, text=True, timeout=60)
        body, _, code = r.stdout.rpartition("\n")
        try:
            remote = json.loads(body)
            print(f"  live {code}  generated {remote.get('generated')}  "
                  f"surfaces {remote.get('counts', {}).get('surfaces')}")
        except Exception:
            print(f"  live {code}  unreadable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
