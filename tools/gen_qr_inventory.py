#!/usr/bin/env python3
"""gen_qr_inventory.py — derive qr_inventory.json from disk.

The inventory is NEVER hand-written. It is generated from the files on disk,
so a surface that appears (or disappears) changes the inventory in the same
commit. Prose drifts from code; code cannot drift from itself.

    python tools/gen_qr_inventory.py            # write qr_inventory.json
    python tools/gen_qr_inventory.py --check    # exit 1 if the file is stale

Roots — the inventory spans two trees on purpose:

    main     C:/æ                engineering source (agents, kænbæn, widget)
    gh-pages C:/æ/github-pages  the deployed truth surface (html, videos)

Each category names its root and its pattern, so a renamed file shows up as a
drift in `--check` instead of silently vanishing from the catalog.

`configs` is pinned: it holds an absolute path and cross-references that cannot
be derived from the filesystem.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent      # C:/æ
GH = ROOT / "github-pages"
OUT = ROOT / "qr_inventory.json"


def scan(root: pathlib.Path, pattern: str, *, twin_mp4: bool = False) -> list[str]:
    """List files under `root` matching `pattern`, as repo-relative POSIX paths.

    twin_mp4=True keeps only entries that also have a .mp4 beside them — the
    rule the teologia scenes follow (a scene without its rendered video is not
    a scene yet).
    """
    if not root.exists():
        return []
    out: list[str] = []
    for p in root.glob(pattern):
        if not p.is_file():
            continue
        if twin_mp4 and not p.with_suffix(".mp4").exists():
            continue
        out.append(p.relative_to(root).as_posix())
    return out


def derive() -> dict:
    """Build the inventory from disk, in the file's canonical key order."""
    return {
        "html_surfaces":  sorted(set(scan(GH, "**/*.html"))),
        "python_agents":  sorted(set(scan(ROOT, "agents/*.py"))),
        "threejs_scenes": sorted(set(scan(GH, "teologia/*.html", twin_mp4=True))),
        "videos":         sorted(set(scan(GH, "**/*.mp4"))),
        # Pinned: absolute path + cross-references; not derivable.
        "configs": [
            "C:/æ/qr_inventory.json",
            "widget/manifest.json",
            "kænbæn/capability-contracts.json",
            "kænbæn/genesis-chain.json",
            "kænbæn/system-map.json",
            "kænbæn/verification-gates.json",
        ],
        "logs":    sorted(set(scan(GH, "logs/*"))),
        "widget":  sorted(set(scan(GH, "widget/*")) | set(scan(ROOT, "widget/*"))),
        "kanban":  sorted(set(scan(ROOT, "kænbæn/*"))),
    }


def render(inv: dict) -> str:
    return json.dumps(inv, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="derive qr_inventory.json from disk")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed file differs from disk")
    ap.add_argument("--mirror", action="store_true",
                    help="also write the site/ and github-pages/ copies")
    args = ap.parse_args()

    inv = derive()
    text = render(inv)
    counts = ", ".join(f"{k}={len(v)}" for k, v in inv.items())

    if args.check:
        if not OUT.exists():
            print(f"MISSING: {OUT}", file=sys.stderr)
            return 1
        committed = OUT.read_text(encoding="utf-8")
        if committed != text:
            print(f"STALE: {OUT.name} differs from disk — regenerate and commit",
                  file=sys.stderr)
            print(f"  committed: {counts}", file=sys.stderr)
            return 1
        print(f"OK: {OUT.name} is current ({counts})")
        return 0

    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} — {counts}")

    if args.mirror:
        for mirror in (ROOT / "site" / OUT.name, GH / OUT.name):
            mirror.parent.mkdir(parents=True, exist_ok=True)
            mirror.write_text(text, encoding="utf-8")
            print(f"  mirrored -> {mirror}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
