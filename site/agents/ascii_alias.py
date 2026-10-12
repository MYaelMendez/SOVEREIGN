#!/usr/bin/env python3
"""
ascii_alias.py — generate the ASCII alias for every rune-named artifact.

THE RECURRING TAX
-----------------
github.io does not resolve raw UTF-8 in URLs. `/væult/`, `/væult-chain.json`,
`/agents/kænbæn_vault-expectations.md` all 404; only the percent-encoded or
ASCII-alias form resolves.

This has cost a cycle FOUR times in one session — the vault, the chain manifest,
the QR cards, and the expectations doc — and each time the fix was the same
manual copy. That is a tax paid by remembering, which means it will be forgotten.

THE FIX
-------
Generate the alias. One rule, applied automatically:

    rune path  ->  ASCII path
    æ / Æ      ->  ae / AE
    other runes -> transliterated

An artifact whose name contains no rune needs no alias.

USAGE
    python ascii_alias.py check      # which rune paths lack an alias?
    python ascii_alias.py make       # create every missing alias
    python ascii_alias.py name "væult-chain.json"   # what would the alias be?
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sys
import unicodedata

# Runes we actually use, and their ASCII forms. Explicit is better than a
# generic transliteration here: we want the alias to be TYPEABLE, and "ae" is
# what a person types for "æ".
RUNES = {
    "æ": "ae", "Æ": "AE",
    "ø": "o", "Ø": "O",
    "å": "a", "Å": "A",
    "ä": "a", "ö": "o", "ü": "u",
    "é": "e", "è": "e", "ê": "e", "á": "a", "í": "i", "ó": "o", "ú": "u", "ñ": "n",
}


def has_rune(name: str) -> bool:
    return any(ord(ch) > 127 for ch in name)


def to_ascii(name: str) -> str:
    """The alias for a rune path. Idempotent: an ASCII name maps to itself."""
    out = []
    for ch in name:
        if ord(ch) < 128:
            out.append(ch)
        elif ch in RUNES:
            out.append(RUNES[ch])
        else:
            # fall back to a decomposition, then drop anything left
            d = unicodedata.normalize("NFKD", ch)
            out.append("".join(c for c in d if ord(c) < 128) or "_")
    return "".join(out)


def scan(root: pathlib.Path, skip_dirs=(".git", "node_modules", "__pycache__",
                                         "venv", ".venv", "threejs-curriculum",
                                         "teologia", "internetofagents-frames",
                                         "internetofagents-v2-frames")):
    """Every rune-named path under root, and whether its alias exists."""
    found = []
    for p in root.rglob("*"):
        if any(part in skip_dirs for part in p.parts):
            continue
        if not has_rune(p.name):
            continue
        alias = p.with_name(to_ascii(p.name))
        found.append({"path": p, "alias": alias, "alias_exists": alias.exists(),
                      "kind": "dir" if p.is_dir() else "file"})
    return found


def make(root: pathlib.Path, dry: bool = False) -> dict:
    """Create every missing alias. Returns what was made."""
    made, skipped = [], []
    for item in scan(root):
        if item["alias_exists"]:
            skipped.append(str(item["alias"]))
            continue
        src, dst = item["path"], item["alias"]
        if dry:
            made.append(f"{src} -> {dst} (dry)")
            continue
        try:
            if item["kind"] == "dir":
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            made.append(f"{src.name} -> {dst.name}")
        except Exception as e:
            made.append(f"FAILED {src.name}: {e}")
    return {"made": made, "skipped": skipped}


def main(argv):
    ap = argparse.ArgumentParser(description="generate ASCII aliases for rune paths")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check"); c.add_argument("--root", default=r"C:\æ\github-pages")
    m = sub.add_parser("make");  m.add_argument("--root", default=r"C:\æ\github-pages")
    m.add_argument("--dry", action="store_true")
    n = sub.add_parser("name");  n.add_argument("name")

    a = ap.parse_args(argv[1:])

    if a.cmd == "name":
        print(to_ascii(a.name))
        return 0

    if a.cmd == "check":
        items = scan(pathlib.Path(a.root))
        missing = [i for i in items if not i["alias_exists"]]
        print(f"  {len(items)} rune path(s) under {a.root}")
        print(f"  {len(missing)} lack an ASCII alias\n")
        for i in missing:
            print(f"    ✗ {i['path'].relative_to(pathlib.Path(a.root))}")
            print(f"      -> {i['alias'].name}")
        if not missing:
            print("  ✓ every rune path has a resolvable alias")
        return 0 if not missing else 1

    if a.cmd == "make":
        r = make(pathlib.Path(a.root), dry=a.dry)
        for x in r["made"]:
            print(f"  + {x}")
        print(f"\n  {len(r['made'])} made, {len(r['skipped'])} already present")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
