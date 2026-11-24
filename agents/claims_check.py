#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""æ:// claims check — which figures on a surface are read, and which are typed?

The estate rule is "measured, not declared". This is the instrument for it: for
each surface it asks two questions.

  READ      does the page fetch a machine artifact (fetch('*.json'))? If yes, the
            figures it renders may come from there.
  TYPED     are there numeric literals in the MARKUP (script and style stripped)
            that do NOT appear anywhere in the artifacts it fetches? Those are
            hand-written figures — claims, not measurements — unless they are
            dimensions, thresholds or indices.

No opinions. It prints a table and exits 1 if any typed figure is found that is
neither sourced nor plausibly structural.

    python agents/claims_check.py            # the ten representative surfaces
    python agents/claims_check.py --all      # every html surface
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PAGES = Path(r"C:\æ\github-pages")

SURFACES = [
    "index.html", "robots.html", "purpose.html", "waetz.html", "tinyfanin.html",
    "pet/test-916.html", "aipodcast_me/robot-env-demo.html", "tinyae.html",
    "tinyhq.html", "origin/index.html",
]

SKIP_TAGS = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")
COMMENT = re.compile(r"<!--.*?-->", re.S)
FETCH = re.compile(r"""fetch\(\s*['"]([^'"]+)['"]""")
NUM = re.compile(r"(?<![\w.])\d[\d_,]*(?:\.\d+)?(?![\w])")
# A resolution or a viewport is ONE figure, not two: 1536x1872, 135×240. Collapse
# the pair so its halves are not reported as hand-written integers.
DIM = re.compile(r"(\d[\d_,]*)\s*[x×]\s*(\d[\d_,]*)")

# A number that is structural, not a claim: a dimension, a threshold, an index,
# a ratio, a year in prose, a hash fragment.
STRUCTURAL = re.compile(
    r"^\d{1,2}$"                       # small integers: indices, frame counts
    r"|^\d+x\d+$"                      # resolution
    r"|^[\d.]+[x×]$"                   # scale factor
    r"|^(19|20)\d{2}$"                 # year
)


def markup_of(text: str) -> str:
    return TAG.sub(" ", COMMENT.sub(" ", SKIP_TAGS.sub(" ", text)))


def artifacts(text: str, page: Path) -> list[str]:
    """Artifact paths the page fetches, resolved against the page directory."""
    out = []
    for raw in FETCH.findall(text):
        if re.match(r"^(https?:|//|data:|#)", raw, re.I):
            continue
        p = (page.parent / raw.split("?")[0].split("#")[0]).resolve()
        try:
            p.relative_to(PAGES.resolve())
        except ValueError:
            continue
        out.append(str(p))
    return sorted(set(out))


def numbers_in(paths: list[str]) -> set[str]:
    vals: set[str] = set()
    for s in paths:
        f = Path(s)
        if not f.exists():
            continue
        try:
            blob = json.dumps(json.loads(f.read_text(encoding="utf-8")),
                              ensure_ascii=False)
        except Exception:
            blob = f.read_text(encoding="utf-8", errors="replace")
        vals.update(NUM.findall(blob.replace(",", "")))
    return {v.lstrip("0") or "0" for v in vals}


def check(rel: str) -> dict:
    path = PAGES / rel
    rec = {"surface": rel, "exists": path.exists(), "fetches": [], "figures": 0,
           "typed": [], "sourced": 0, "structural": 0}
    if not path.exists():
        return rec
    text = path.read_text(encoding="utf-8", errors="replace")
    arts = artifacts(text, path)
    rec["fetches"] = [Path(a).name for a in arts]
    known = numbers_in(arts)

    mk = markup_of(text)
    rec["dims"] = [f"{a}x{b}" for a, b in DIM.findall(mk)]
    mk = DIM.sub(" ", mk)
    hits = [(m.group(0), mk[max(0, m.start() - 28):m.end() + 14].replace("\n", " "),
             mk[m.end():m.end() + 10], mk[max(0, m.start() - 8):m.start()])
            for m in NUM.finditer(mk)]
    rec["figures"] = len(hits)
    UNIT = re.compile(r"^\s*(Hz|kHz|MHz|GHz|GB|MB|TB|KB|W|ms|s|fps|x|px|kWh|nm)\b", re.I)
    MODEL = re.compile(r"(RTX|GTX|Radeon|GeForce|RTX)\s*$", re.I)
    for v, ctx, after, before in hits:
        norm = v.replace(",", "")
        bare = norm.lstrip("0") or "0"
        if bare in known:
            rec["sourced"] += 1
        elif STRUCTURAL.match(norm) or "." in norm or UNIT.match(after) or MODEL.search(before):
            rec["structural"] += 1
        else:
            rec["typed"].append({"value": v, "context": ctx.strip()})
    return rec


def main() -> int:
    surfs = SURFACES
    if "--all" in sys.argv:
        surfs = [str(p.relative_to(PAGES)).replace("\\", "/")
                 for p in sorted(PAGES.rglob("*.html")) if ".git" not in p.parts]
    rows = [check(s) for s in surfs]
    print(f"{'surface':46} {'figs':>4} {'src':>4} {'struct':>6} {'typed':>5}  fetches")
    flagged = 0
    for r in rows:
        t = len(set(x["value"] for x in r["typed"]))
        flagged += t
        print(f"{r['surface']:46} {r['figures']:>4} {r['sourced']:>4} "
              f"{r['structural']:>6} {t:>5}  {', '.join(r['fetches'][:3])}")
        for t in sorted(set(x["value"] for x in r["typed"]))[:8]:
            ctx = next((x["context"] for x in r["typed"] if x["value"] == t), "")
            print(f"      typed: {t:<10} …{ctx}…")
    print(f"\n{len(rows)} surfaces · {sum(r['figures'] for r in rows)} figures · "
          f"{flagged} typed (unsourced, non-structural)")
    doc = {"schema": "æ-claims-check/1", "surfaces": rows,
           "counts": {"surfaces": len(rows),
                      "figures": sum(r["figures"] for r in rows),
                      "sourced": sum(r["sourced"] for r in rows),
                      "structural": sum(r["structural"] for r in rows),
                      "typed": flagged}}
    (PAGES / "claims-check.json").write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {PAGES / 'claims-check.json'}")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
