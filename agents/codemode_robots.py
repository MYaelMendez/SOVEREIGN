#!/usr/bin/env python3
"""codemode://robots — the fleet as an expression, not a tool call.

The thesis: a tool call is one narrow round trip; an expression is arbitrary
composition in the model's native I/O. So the fleet is exposed as a small
namespace the agent addresses by writing code:

    codemode://robots "present()"                    → ['asimov','microduck','reachy']
    codemode://robots "coverage('reachy')"          → 100
    codemode://robots "provides('asimov','plan')"    → 'trajectory (plan only — never acts)'
    codemode://robots "mesh_only()"                 → the named gaps

GOVERNED, not free eval. Two hard rules, because this is code:

  1. No dunder. `__` anywhere in the expression is refused, so the classic
     `().__class__.__mro__` escape has no surface. `__builtins__` is empty.
  2. Only the whitelist below is reachable. A name outside it is a refusal.

And every evaluation leaves a receipt — the hash of the expression and the
result — because execution you cannot check back is not a result.

    codemode://robots "<expr>"      evaluate, print JSON
    codemode://robots --repl        read-eval-print (still governed)
    codemode://robots --ledger [N]  the receipt chain
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import robot_index  # noqa: E402
import robot_protocol as rp  # noqa: E402

LEDGER = ROOT / "logs" / "codemode" / "robots.jsonl"
INDEX_PATH = ROOT / "robots" / "index.json"

_ALLOWED_NAMES = {
    "fleet", "robots", "roster", "categories", "meshes", "standard_interface",
    "present", "mesh_only", "coverage", "provides", "verb_classes", "transports",
    "ledger_receipts", "policy_sha256", "unregistered", "gaps", "sha", "len",
    "sorted", "sum", "min", "max", "abs", "round", "list", "tuple", "dict", "str",
    "int", "float", "bool", "receipt",
}


class Refused(Exception):
    pass


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=str)


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
    body = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "action": action, "detail": detail, "prev": _last_hash()}
    body["hash"] = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(_canonical(body) + "\n")
    return body


def load_index() -> dict:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def namespace() -> dict:
    d = load_index()
    r = d["robots"]

    def present():
        return [n for n in d["roster"] if r[n].get("present")]

    def mesh_only():
        return [n for n in d["roster"] if not r[n].get("present")]

    def coverage(n):
        return r[n]["coverage"] if n in r else None

    def provides(n, v):
        return (r[n].get("provides") or {}).get(v) if n in r else None

    def verb_classes(n):
        return r[n].get("verb_classes", {}) if n in r else None

    def transports(n):
        return r[n].get("transports", []) if n in r else None

    def ledger_receipts(n):
        return r[n].get("ledger_receipts", 0) if n in r else None

    def policy_sha256(n):
        return r[n].get("policy_sha256") if n in r else None

    def unregistered():
        return d.get("unregistered_dialects", [])

    def gaps():
        return {
            "mesh_only": mesh_only(),
            "in_category_absent_from_roster": sorted(
                n for c in d.get("categories", {}).values() for n in c if n not in r),
            "unregistered_dialects": unregistered(),
        }

    return {
        "fleet": d, "robots": r, "roster": d["roster"],
        "categories": d.get("categories", {}), "meshes": d.get("meshes", []),
        "standard_interface": d.get("standard_interface", []),
        "present": present, "mesh_only": mesh_only, "coverage": coverage,
        "provides": provides, "verb_classes": verb_classes,
        "transports": transports, "ledger_receipts": ledger_receipts,
        "policy_sha256": policy_sha256, "unregistered": unregistered, "gaps": gaps,
        "sha": lambda s: hashlib.sha256(str(s).encode("utf-8")).hexdigest(),
        "receipt": lambda a, d2=None: receipt(a, d2 or {}),
        "len": len, "sorted": sorted, "sum": sum, "min": min, "max": max,
        "abs": abs, "round": round, "list": list, "tuple": tuple, "dict": dict,
        "str": str, "int": int, "float": float, "bool": bool,
    }


def validate(expr: str) -> None:
    """Refuse before evaluating. No dunder, no name outside the whitelist.

    String literals are stripped first: a robot name inside quotes is data,
    not a name to whitelist.
    """
    if "__" in expr:
        raise Refused("dunder refused — no __ anywhere")
    stripped = re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", '""', expr)
    for name in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", stripped):
        if name in ("None", "True", "False"):
            continue
        if name in ("for", "in", "if", "else", "elif", "and", "or", "not", "is", "lambda"):
            continue          # comprehension / boolean syntax, not a lookup
        if len(name) == 1 and name.islower():
            continue          # loop / comprehension binding (n, i, r, …)
        if name not in _ALLOWED_NAMES:
            raise Refused(f"name {name!r} is not in the whitelist")


def evaluate(expr: str) -> dict:
    validate(expr)
    ns = namespace()
    ns["__builtins__"] = {}
    try:
        out = eval(expr, ns, ns)  # noqa: S307 — governed: no dunder, whitelist
    except Refused as e:
        rec = receipt("refused", {"expr": expr, "reason": str(e)})
        return {"ok": False, "refused": True, "reason": str(e), "receipt": rec["hash"]}
    except Exception as e:
        rec = receipt("error", {"expr": expr, "reason": f"{type(e).__name__}: {e}"})
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "receipt": rec["hash"]}
    rec = receipt("eval", {"expr": expr, "result": out})
    return {"ok": True, "expr": expr, "result": out, "receipt": rec["hash"]}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="codemode://robots")
    p.add_argument("expr", nargs="?")
    p.add_argument("--repl", action="store_true")
    p.add_argument("--ledger", type=int, nargs="?", const=10)
    a = p.parse_args(argv)
    if a.ledger is not None:
        if not LEDGER.exists():
            print("no ledger.")
            return 0
        for l in [x for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()][-a.ledger:]:
            print(l)
        return 0
    if a.repl:
        while True:
            try:
                raw = input("codemode://robots> ")
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if raw.strip() in ("exit", "quit"):
                return 0
            print(json.dumps(evaluate(raw), ensure_ascii=False))
        return 0
    if not a.expr:
        p.error("an expression is required (or --repl / --ledger)")
    try:
        out = evaluate(a.expr)
    except Refused as e:
        rec = receipt("refused", {"expr": a.expr, "reason": str(e)})
        out = {"ok": False, "refused": True, "reason": str(e), "receipt": rec["hash"]}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
