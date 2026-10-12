#!/usr/bin/env python3
"""
teach_check.py — is every agent actually taught to use the chain?

TEACHING IS NOT A SKILL FILE
----------------------------
A skill only loads when its trigger matches. That is not teaching — it is
documentation that hopes to be found. A fleet learns through surfaces it is
FORCED to read:

    1. AGENTS.md              auto-loaded into every agent in C:\\æ
    2. kænbæn system-map      "every agent reads this before acting"
    3. capability-contracts   "what each agent can do — read before dispatching"

If the chain is not in those three, an agent can work a whole session without
knowing it exists. This script checks that it IS, and reports exactly which
surface has drifted.

It also checks the inverse: that the surfaces do not point at things that no
longer exist. A stale instruction is worse than a missing one — it sends an
agent confidently to a dead end.

USAGE
    python teach_check.py            check every surface, exit 1 if any is stale
    python teach_check.py --json     machine-readable
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

BASE = pathlib.Path(os.environ.get("AE_BASE", r"C:\æ"))
AGENTS_MD = BASE / "AGENTS.md"
K_BASE = pathlib.Path(os.environ.get("KAENBAEN_BASE", str(BASE / "kænbæn")))
SYS_MAP = K_BASE / "system-map.json"
SOUL_MD = pathlib.Path(os.environ.get("HERMES_HOME",
    str(pathlib.Path.home() / "AppData" / "Local" / "hermes"))) / "SOUL.md"
CONTRACTS = K_BASE / "capability-contracts.json"

# What a taught agent must be able to find, and where it must be findable.
REQUIRED_TERMS = {
    "AGENTS.md": ["væult", "væult://chain", "kanban_push.py", "agent_pledge.py"],
    "system-map": ["vaeult-chain"],
    "capability-contracts": ["vaeult_chain"],
    # SOUL.md is loaded from HERMES_HOME and is CWD-INDEPENDENT — the only
    # context surface that reaches an agent no matter where it runs.
    "SOUL.md": ["væult_chain.py", "Claim before you act", "Never move a secret"],
}

# A subagent is built with skip_context_files=True, so it inherits neither
# SOUL.md nor AGENTS.md. Its rules must live in a surface that is NOT gated —
# the vaeult-chain plugin section.
#
# The child prompt is built by the RUNNING tree, not the fork: hermes-fork is a
# stale Oct-3 copy, hermes-agent is live. Pointing this at the fork made the old
# check read code no running agent ever executes.
HERMES_TREE = pathlib.Path(os.environ.get(
    "HERMES_TREE",
    str(pathlib.Path.home() / "AppData" / "Local" / "hermes" / "hermes-agent")))
DELEGATE_PROMPT = pathlib.Path(
    os.environ.get("DELEGATE_TOOL", str(HERMES_TREE / "tools" / "delegate_tool.py")))
CHAIN_PLUGIN = pathlib.Path(os.environ.get(
    "CHAIN_PLUGIN",
    str(pathlib.Path.home() / "AppData" / "Local" / "hermes" / "plugins"
        / "vaeult-chain" / "__init__.py")))
SUBAGENT_TERMS = ["væult_chain.py", "Claim before you act", "Never move a secret"]


def _read_text(p: pathlib.Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def _read_json(p: pathlib.Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _child_carries_chain() -> tuple:
    """Build the prompt a delegated child actually gets, and look for the chain.

    Returns (ok, detail, evidence). Never guesses: if the tree cannot be imported
    the result is NOT a pass — an unverifiable surface is reported as
    unverifiable, which is the rule the chain exists to enforce.
    """
    import subprocess
    py = os.environ.get("AE_PYTHON") or str(HERMES_TREE / "venv" / "Scripts" / "python.exe")
    if not pathlib.Path(py).exists():
        py = sys.executable
    script = r'''
import sys, os
sys.path.insert(0, os.environ["TREE"])
from hermes_cli.plugins import discover_plugins, render_system_prompt_sections
discover_plugins()
from agent import system_prompt as sp

class Child:
    skip_context_files = True          # exactly how delegate_tool builds one
    load_soul_identity = False
    platform = "subagent"
    session_id = "20261010_teachcheck"
    valid_tool_names = {"bash", "read_file"}
    model = "check"; provider = "check"
    _plugin_system_prompt_sections_snapshot = render_system_prompt_sections({})
    def __getattr__(self, n):
        if n.startswith("_plugin"): raise AttributeError(n)
        return None

parts = sp.build_system_prompt_parts(Child())
full = "\n\n".join(v for v in parts.values() if v)
print("HAS_CHAIN=%s" % ("væult_chain.py" in full))
print("LEN=%d" % len(full))
print("VOLATILE=%d" % len(parts.get("volatile") or ""))
print("CONTEXT=%d" % len(parts.get("context") or ""))
'''
    env = dict(os.environ, TREE=str(HERMES_TREE))
    try:
        r = subprocess.run([py, "-c", script], capture_output=True, text=True,
                           timeout=120, env=env)
    except Exception as e:
        return False, f"could not build a child prompt: {type(e).__name__}: {e}", {}
    out = r.stdout or ""
    if "HAS_CHAIN=" not in out:
        return False, f"child-prompt probe failed: {(r.stderr or out).strip()[:200]}", {}
    ev = {}
    for line in out.split("\n"):
        if "=" in line:
            k, _, v = line.partition("=")
            if k in ("LEN", "VOLATILE", "CONTEXT"):
                ev[k.lower()] = v.strip()
    ok = "HAS_CHAIN=True" in out
    # context == 0 proves the gating is real; a non-zero context means the probe
    # is not exercising skip_context_files at all, so it would prove nothing.
    if ok and ev.get("context") != "0":
        return False, ("chain present but context tier is non-zero — the probe is "
                       "not exercising skip_context_files, so it proves nothing"), ev
    return ok, ("child carries the chain" if ok
                else "a delegated child does NOT carry the chain"), ev


def check() -> dict:
    results = []

    # 1. AGENTS.md — the highest-reach surface
    md = _read_text(AGENTS_MD)
    missing = [t for t in REQUIRED_TERMS["AGENTS.md"] if t not in md]
    results.append({
        "surface": "AGENTS.md", "path": str(AGENTS_MD),
        "exists": AGENTS_MD.exists(), "reach": "every agent in C:\\æ (auto-loaded)",
        "required": REQUIRED_TERMS["AGENTS.md"], "missing": missing,
        "ok": AGENTS_MD.exists() and not missing,
    })

    # 2. system-map — "every agent reads this before acting"
    smap = _read_json(SYS_MAP)
    surfaces = smap.get("surfaces", {})
    missing = [t for t in REQUIRED_TERMS["system-map"] if t not in surfaces]
    results.append({
        "surface": "kænbæn system-map", "path": str(SYS_MAP),
        "exists": SYS_MAP.exists(), "reach": "every agent reads this before acting",
        "required": REQUIRED_TERMS["system-map"], "missing": missing,
        "ok": SYS_MAP.exists() and not missing,
    })

    # 3. capability-contracts — what each agent can do
    con = _read_json(CONTRACTS)
    agents = con.get("agents", {})
    # an agent may be registered under its canonical name with aliases; the
    # chain is present if ANY of them resolves.
    known = set(agents.keys())
    for _n, _a in agents.items():
        known.update(_a.get("aliases", []))
    missing = [t for t in REQUIRED_TERMS["capability-contracts"] if t not in known]
    results.append({
        "surface": "capability-contracts", "path": str(CONTRACTS),
        "exists": CONTRACTS.exists(), "reach": "read before dispatching",
        "required": REQUIRED_TERMS["capability-contracts"], "missing": missing,
        "ok": CONTRACTS.exists() and not missing,
    })

    # 3b. SOUL.md — the ONLY cwd-independent surface. AGENTS.md is anchored to
    # the working directory and only walks DOWN, so an agent running in
    # C:\æ\agents or C:\Users\yaelm gets nothing from it.
    soul = _read_text(SOUL_MD)
    missing = [x for x in REQUIRED_TERMS["SOUL.md"] if x not in soul]
    results.append({
        "surface": "SOUL.md", "path": str(SOUL_MD),
        "exists": SOUL_MD.exists(), "reach": "every agent, ANY cwd (HERMES_HOME)",
        "required": REQUIRED_TERMS["SOUL.md"], "missing": missing,
        "ok": SOUL_MD.exists() and not missing,
    })

    # 3c. THE SUBAGENT — the surface that matters most and was hardest to reach.
    # Children are built with skip_context_files=True, so SOUL.md and AGENTS.md
    # never load for them; a child inherited the chain only by accident of its
    # workspace path. Measured before the fix: 0 of 116 stored subagent prompts
    # carried it.
    #
    # This does NOT grep a source file — that was the old bug, and it passed
    # while every child was blind. It builds the prompt a real child gets and
    # asserts the chain is in it.
    child_ok, child_detail, child_evidence = _child_carries_chain()
    results.append({
        "surface": "subagent prompt", "path": str(CHAIN_PLUGIN),
        "exists": CHAIN_PLUGIN.exists(),
        "reach": "every delegated child (skip_context_files=True)",
        "required": SUBAGENT_TERMS,
        "missing": [] if child_ok else SUBAGENT_TERMS,
        "ok": child_ok,
        "detail": child_detail, "evidence": child_evidence,
    })

    # 3d. THE REGISTRY MUST BE TRUE (E6). Every registered path resolves, and
    # every `cannot` is in the `cannot` list — not stuffed into `can`.
    # An agent contract that lies about itself is the first thing to fix.
    reg_bad = []
    for name, a in agents.items():
        if a.get("status") == "scratch":
            continue
        for pth in [a.get("path", "")] + list(a.get("also", [])):
            if pth and not pathlib.Path(pth).exists():
                reg_bad.append(f"{name}: dead path {pth}")
        stuffed = [x for x in a.get("can", []) if str(x).startswith("cannot:")]
        if stuffed:
            reg_bad.append(f"{name}: {len(stuffed)} cannot(s) stuffed into can")
    results.append({
        "surface": "registry is true", "path": str(CONTRACTS),
        "exists": CONTRACTS.exists(), "reach": "an agent contract that lies about itself",
        "required": ["every path resolves", "cannots live in cannot"],
        "missing": reg_bad, "ok": not reg_bad,
    })

    # 3e. RUNE PATHS MUST RESOLVE. github.io does not serve raw UTF-8 in URLs,
    # so a rune-named artifact is unreachable without an ASCII alias. This cost
    # a cycle four times; now it is checked instead of remembered.
    try:
        import ascii_alias as aa
        gp = pathlib.Path(os.environ.get("GITHUB_PAGES", r"C:\æ\github-pages"))
        rune_paths = aa.scan(gp)
        unaliased = [str(i["path"].relative_to(gp)) for i in rune_paths
                     if not i["alias_exists"]]
    except Exception as e:
        unaliased = [f"could not scan: {type(e).__name__}"]
    results.append({
        "surface": "rune paths resolve", "path": "github-pages",
        "exists": True, "reach": "a rune path 404s on github.io without an alias",
        "required": ["every rune path has an ASCII alias"],
        "missing": unaliased, "ok": not unaliased,
    })

    # 4. INVERSE CHECK — do the surfaces point at files that exist?
    # A stale instruction is worse than a missing one.
    dead = []
    chain = BASE / "agents" / "væult_chain.py"
    if "væult_chain.py" in md and not chain.exists():
        dead.append({"referenced": str(chain), "in": "AGENTS.md"})
    for name, rel in (("kanban_push.py", "agents/kanban_push.py"),
                      ("agent_pledge.py", "agents/agent_pledge.py")):
        if name in md and not (BASE / rel).exists():
            dead.append({"referenced": str(BASE / rel), "in": "AGENTS.md"})
    if "vaeult-chain" in surfaces:
        m = surfaces["vaeult-chain"].get("cli", "")
        p = m.split("python", 1)[-1].strip() if "python" in m else ""
        if p and not pathlib.Path(p).exists():
            dead.append({"referenced": p, "in": "system-map"})
    results.append({
        "surface": "pointers resolve", "path": "-",
        "exists": True, "reach": "a stale instruction sends an agent to a dead end",
        "required": ["every referenced path exists"], "missing": [d["referenced"] for d in dead],
        "ok": not dead, "dead": dead,
    })

    ok = all(r["ok"] for r in results)
    return {"ok": ok, "surfaces": results,
            "taught": sum(1 for r in results if r["ok"]), "total": len(results)}


def main(argv):
    ap = argparse.ArgumentParser(description="is every agent taught to use the chain?")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv[1:])

    r = check()
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0 if r["ok"] else 1

    print(f"TEACHING CHECK — {r['taught']}/{r['total']} surfaces carry the chain\n")
    for s in r["surfaces"]:
        mark = "✓" if s["ok"] else "✗"
        print(f"  {mark} {s['surface']}")
        print(f"      reach: {s['reach']}")
        if s["missing"]:
            print(f"      MISSING: {', '.join(s['missing'])}")
        if s.get("dead"):
            for d in s["dead"]:
                print(f"      DEAD POINTER: {d['referenced']} (referenced in {d['in']})")
    if not r["ok"]:
        print("\n  An agent can work a whole session without knowing the chain exists.")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
