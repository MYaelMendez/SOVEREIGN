#!/usr/bin/env python3
"""gen_capability_manifest.py — derive the capability catalog from the bindings.

The catalog is NEVER hand-written. It is generated from the live DSL bindings in
agents/æ_code_mode.py, so the schema and the behavior are the same file: a
capability that changes its signature changes its manifest hash in the same
commit. Prose drifts from code; code cannot drift from itself.

    python tools/gen_capability_manifest.py           # write capability-manifest.json
    python tools/gen_capability_manifest.py --check   # exit 1 if the file is stale

Safety: the substrate is *imported* (module-level code only — class defs, no I/O).
Binding method bodies (ledger writes, broker probes) run only when called, so the
generator never triggers a side effect.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUBSTRATE = ROOT / "agents" / "æ_code_mode.py"
OUT = ROOT / "capability-manifest.json"

# Real credential shapes, not substrings — "sk-" alone matches "task-id"/"risk-".
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),              # OpenAI-style
    re.compile(r"AKIA[0-9A-Z]{16}"),                 # AWS access key id
    re.compile(r"ghp_[A-Za-z0-9]{36}"),              # GitHub PAT
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def load_substrate():
    """Import agents/æ_code_mode.py by path. Import is safe — no module-level I/O."""
    spec = importlib.util.spec_from_file_location("ae_code_mode", str(SUBSTRATE))
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load substrate at {SUBSTRATE}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(with_skills: bool = False) -> dict:
    """Build the manifest payload.

    Deterministic: no timestamp, and capabilities only by default. The skill half
    is machine-local (it reads the local skills dirs), so embedding it would make
    --check fail on any other machine. Skills stay a live query (æ.skills()); the
    committed manifest is the machine-independent capability surface.
    """
    mod = load_substrate()
    æ = mod._Æ()  # constructor instantiates bindings only — no I/O
    caps = æ.manifest()
    src = SUBSTRATE.read_bytes()
    payload = {
        "scheme": "æ://capabilities",
        "generated_from": "agents/æ_code_mode.py",
        "source_sha256": hashlib.sha256(src).hexdigest(),
        "count": len(caps),
        "capabilities": caps,
    }
    if with_skills:
        skills = æ.skills(limit=1000)
        payload["skills_count"] = len(skills)
        payload["skills"] = [{"name": s["name"], "description": s["description"], "tags": s["tags"]}
                             for s in skills]
    return payload


def render(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=1) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="generate the æ capability manifest")
    ap.add_argument("--check", action="store_true", help="fail if the committed manifest is stale")
    ap.add_argument("--with-skills", action="store_true",
                    help="also embed the local skill index (machine-local; not for the gated file)")
    args = ap.parse_args(argv)

    payload = build(with_skills=args.with_skills)
    text = render(payload)

    # secret gate — the manifest must never carry a credential
    for pat in SECRET_PATTERNS:
        if pat.search(text):
            print(f"REFUSED: manifest matches secret pattern {pat.pattern}", file=sys.stderr)
            return 2

    if args.check:
        if not OUT.exists():
            print(f"STALE: {OUT.name} does not exist — run the generator", file=sys.stderr)
            return 1
        committed = OUT.read_text(encoding="utf-8")
        if committed != text:
            print(f"STALE: {OUT.name} differs from the bindings — regenerate and commit",
                  file=sys.stderr)
            return 1
        extra = f", {payload['skills_count']} skills" if "skills_count" in payload else ""
        print(f"OK: {OUT.name} is current ({payload['count']} capabilities{extra})")
        return 0

    OUT.write_text(text, encoding="utf-8")
    extra = f", {payload['skills_count']} skills" if "skills_count" in payload else ""
    print(f"wrote {OUT} — {payload['count']} capabilities{extra}, "
          f"source {payload['source_sha256'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
