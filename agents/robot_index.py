#!/usr/bin/env python3
"""robot index — one development contract, every robot measured against it.

The rule this encodes: whatever we build for ONE robot, we provide for ALL.
So the index is not a list of robots; it is the STANDARD INTERFACE every robot
is expected to implement, with a MEASURED verdict per robot.

    robot://<robot>/<verb>     the address
    status                     present? transports? live? ledger tail?
    verbs                      the verb table, hashed (the policy IS the verbs)
    plan <command>             a plan, never an act (address != permission)
    sim <command>              the simulation trace, receipted
    exec <command>             hardware — requires approval, stays dry-run
    receipt                    the ledger, hash-chained
    ledger                     the ledger tail, verifiable

`provides_measured` is DERIVED from each dialect's own verb classes — never
hand-typed — and the human-readable `provides` must agree with it. Evidence
(module bytes, verb table, ledger tail) is read from disk; a missing file is
null, never a guess. Generated from `rp.doctor()` + `rp.fleet_anchor()`.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import robot_protocol as rp  # noqa: E402

GLB_DIR = ROOT / "github-pages" / "assets" / "gltf"

# The development contract. Every robot is measured against these seven.
STANDARD_INTERFACE = ["status", "verbs", "plan", "sim", "exec", "receipt", "ledger"]

# Categories the estate actually names. A robot may be in more than one.
CATEGORIES = {
    "humanoid": ["asimov", "kira", "Xbot", "Soldier"],
    "companion": ["asimov_pet", "tinyasimov"],
    "lab": ["reachy", "microduck", "microduck_rl"],
    "phone": [],
    "drone": [],
}

# Bodies that exist as meshes but have no dialect and no policy.
MESH_ONLY = ["kira", "Xbot", "Soldier"]

# Human-readable display text, kept for the surface. It is NOT the measurement:
# `provides_measured` is derived below, and the two must agree or the build fails.
PROVIDES = {
    "asimov": {
        "status": "status / state / get_state",
        "verbs": "the dialect's own table (14)",
        "plan": "trajectory (plan only — never acts)",
        "sim": "sim transport (MuJoCo, via tinypython)",
        "exec": "set_velocity / set_joints — gated, dry-run",
        "receipt": "asimov-protocol.jsonl",
        "ledger": "asimov-protocol.jsonl",
    },
    "reachy": {
        "status": "imu / get_current_*",
        "verbs": "the dialect's own table (27)",
        "plan": "goto_target / set_target (gated)",
        "sim": "sim transport (MockupSim)",
        "exec": "set_target_* — gated, dry-run",
        "receipt": "reachy-protocol.jsonl",
        "ledger": "reachy-protocol.jsonl",
    },
    "microduck": {
        "status": "health / system.info",
        "verbs": "the dialect's own table (22)",
        "plan": "robot.move (gated)",
        "sim": "sim transport (duck-sim)",
        "exec": "robot.do — gated, dry-run",
        "receipt": "microduck-protocol.jsonl",
        "ledger": "microduck-protocol.jsonl",
    },
    # mesh bodies: rigs on disk, no vendor SDK, no physics, no actuators.
    # The same seven routes exist; the physical ones refuse by name.
    "Soldier": {
        "status": "mesh facts (GLB, measured)",
        "verbs": "the dialect's own table (7: 5 read, 2 render)",
        "plan": "render/animate — refused by name for the physical",
        "receipt": "meshbot-protocol.jsonl",
        "ledger": "meshbot-protocol.jsonl",
    },
    "Xbot": {
        "status": "mesh facts (GLB, measured)",
        "verbs": "the dialect's own table (7: 5 read, 2 render)",
        "plan": "render/animate — refused by name for the physical",
        "receipt": "meshbot-protocol.jsonl",
        "ledger": "meshbot-protocol.jsonl",
    },
    "kira": {
        "status": "mesh facts (GLB, measured)",
        "verbs": "the dialect's own table (7: 5 read, 2 render)",
        "plan": "render/animate — refused by name for the physical",
        "receipt": "meshbot-protocol.jsonl",
        "ledger": "meshbot-protocol.jsonl",
    },
}

# Which verb classes satisfy each standard verb. DERIVED, never typed per robot:
# a standard verb is provided iff the dialect's own table has a verb of a class
# that can satisfy it. Render verbs can be planned without hardware; motion
# verbs are what plan/exec/sim need. `verbs` is satisfied by the table existing.
CLASS_SATISFIES = {
    "status": ("read", "render"),
    "verbs": (),            # any verb at all — the table itself is the proof
    "plan": ("motion", "render"),
    "sim": ("motion",),
    "exec": ("motion",),
    "receipt": ("read", "render"),
    "ledger": ("read", "render"),
}


def provides_measured(classes: dict) -> dict:
    """Derive the standard-interface verdict from the dialect's own classes."""
    out = {}
    for v in STANDARD_INTERFACE:
        out[v] = bool(classes) if v == "verbs" \
            else bool(set(classes) & set(CLASS_SATISFIES[v]))
    return out


def assert_provides_agree(name: str, provides: dict, measured: dict) -> None:
    """A declared `provides` that disagrees with the measurement fails loudly."""
    bad = [v for v in STANDARD_INTERFACE
           if bool(provides.get(v)) != bool(measured.get(v))]
    if bad:
        detail = "; ".join(f"{v} declared={provides.get(v)!r} measured={measured.get(v)}"
                           for v in bad)
        raise AssertionError(f"{name}: provides disagrees with provides_measured ({detail})")


# Dialects on disk, keyed by DIALECT (the module stem), NOT by robot: one dialect
# may serve several bodies — meshbot serves Soldier, Xbot and kira, sharing one
# ledger. A registered dialect missing from either map is a named gap, not a
# silent null.
DIALECT_MODULE = {
    "asimov": "asimov_protocol.py",
    "reachy": "reachy_protocol.py",
    "microduck": "microduck_protocol.py",
    "meshbot": "meshbot_protocol.py",
}
LEDGER_FILE = {
    "asimov": "asimov-protocol.jsonl",
    "reachy": "reachy-protocol.jsonl",
    "microduck": "microduck-protocol.jsonl",
    "meshbot": "meshbot-protocol.jsonl",
}


def _dialect_of(name: str) -> str:
    module = (rp.ROBOTS.get(name) or {}).get("module") or ""
    return module[:-len("_protocol")] if module.endswith("_protocol") else name


def _require_dialect_registry(dialects) -> None:
    """Every registered dialect must declare its module and ledger file."""
    missing = sorted(d for d in dialects
                     if d not in DIALECT_MODULE or d not in LEDGER_FILE)
    if missing:
        raise AssertionError(
            f"DIALECT_MODULE/LEDGER_FILE incomplete for registered dialect(s): {missing}")


def _ledger_in_estate(name: str) -> bool:
    """Can a reader of the published site check this ledger tail?

    Measured in the generator: if the ledger lives outside github-pages its hash
    cannot be re-derived from anything on the surface, and the page must say so.
    """
    try:
        p = rp.resolve_ledger({}, name)
    except Exception:
        return False
    return bool(p.is_file()) and 'github-pages' in str(p).replace('\\', '/')


def dialect_evidence(name: str, table: dict | None = None) -> dict:
    """Evidence measured from disk, plus the dialect's own policy hash."""
    meta = rp.ROBOTS.get(name) or {}
    ev = rp.dialect_evidence(name, meta)
    if table is None:
        try:
            mod = rp._load(meta.get("module"))
            table = rp._table_from_verbs(rp._dialect_verbs(mod, meta, name))
        except Exception:
            table = {}
    ev["policy_sha256"] = rp._policy_sha(table) if table else None
    return ev


def build() -> dict:
    # rp.doctor(), not rp.dispatch("robot://doctor"): a generator must not append
    # to the very chain it measures. doctor() probes; it does not record.
    doc = rp.doctor()
    anchor = rp.fleet_anchor()
    robots = doc.get("robots", {})

    dialects = {_dialect_of(n) for n in robots} | {_dialect_of(b) for b in MESH_ONLY}
    _require_dialect_registry(sorted(dialects))

    out_robots = {}
    for name, meta in robots.items():
        reg = rp.ROBOTS.get(name, {})
        try:
            mod = rp._load(reg.get("module") or meta.get("module"))
            table = rp._table_from_verbs(rp._dialect_verbs(mod, reg, name))
        except Exception:
            mod, table = None, {}
        classes = {c: sum(1 for v in table.values() if v == c)
                   for c in sorted(set(table.values()))}
        provides = {v: PROVIDES.get(name, {}).get(v) for v in STANDARD_INTERFACE}
        measured = provides_measured(classes)
        assert_provides_agree(name, provides, measured)

        rule = None
        if mod is not None:
            try:
                fn = getattr(mod, "status_for", None)
                st = fn(reg.get("body") or name) if fn else mod.status()
                rule = (st or {}).get("rule")
            except Exception:
                pass

        out_robots[name] = {
            "scheme": meta.get("scheme"),
            "sdk": meta.get("sdk"),
            "present": meta.get("present"),
            "live": meta.get("live"),
            "verbs": meta.get("verbs"),
            "verb_classes": classes,
            "transports": meta.get("transports"),
            "ledger_receipts": (meta.get("ledger") or {}).get("receipts"),
            "policy_sha256": meta.get("policy_sha256"),
            "provides": provides,
            "provides_measured": measured,
            "rule": rule,
            "evidence": {**dialect_evidence(name, table),
                         "ledger_in_estate": _ledger_in_estate(name)},
            "evidence_kind": "measured — verb classes, module bytes and ledger tail "
                             "read from disk; provides_measured derived from those classes",
            "coverage": round(100 * sum(1 for v in STANDARD_INTERFACE if measured[v])
                              / len(STANDARD_INTERFACE)),
        }

    # bodies on disk that have no dialect at all
    meshes = sorted(p.stem for p in GLB_DIR.glob("*.glb"))
    for body in MESH_ONLY:
        if body not in out_robots:
            out_robots[body] = {
                "scheme": None, "sdk": None, "present": False, "live": False,
                "verbs": 0, "verb_classes": {}, "transports": [],
                "ledger_receipts": 0, "policy_sha256": None,
                "provides": {v: None for v in STANDARD_INTERFACE},
                "provides_measured": {v: False for v in STANDARD_INTERFACE},
                "coverage": 0, "reason": "mesh only — no dialect, no policy",
                "evidence": {"module": None, "module_bytes": 0,
                             "verb_table_present": False, "ledger_file": None,
                             "ledger_bytes": 0, "ledger_tail": None,
                             "policy_sha256": None},
            }

    roster = sorted(out_robots)
    return {
        "schema": "robot-index/2",
        "authority": rp.AUTHORITY,
        "generated": rp.datetime.now(rp.timezone.utc).isoformat(timespec="seconds"),
        "standard_interface": STANDARD_INTERFACE,
        "categories": CATEGORIES,
        "roster": roster,
        "count": len(roster),
        "robots": out_robots,
        "unregistered_dialects": doc.get("unregistered_dialects"),
        "meshes": meshes,
        "ledger": anchor,
        "coverage_kind": "measured — provides_measured is derived from each dialect's "
                         "own verb classes (read/render satisfy status/verbs/receipt/ledger; "
                         "motion satisfies plan/exec/sim); module bytes and ledger tails "
                         "are read from disk, and the human `provides` must agree",
        "rule": "whatever is built for one robot is provided for all; a missing "
                "verb is a named refusal, never a crash",
    }


def main() -> int:
    p = argparse.ArgumentParser(prog="robot-index")
    p.add_argument("--out", default=str(ROOT / "robots" / "index.json"))
    p.add_argument("--check", action="store_true",
                   help="fail 1 if the committed index differs from disk-derived truth")
    a = p.parse_args()
    doc = build()
    out = pathlib.Path(a.out)
    if a.check:
        if not out.exists():
            print("MISSING: " + str(out), file=sys.stderr)
            return 1
        cur = json.loads(out.read_text(encoding="utf-8"))
        keys = [k for k in doc if k != "generated"]
        if any(cur.get(k) != doc[k] for k in keys):
            print("STALE: robots/index.json differs from disk — regenerate", file=sys.stderr)
            return 1
        print(f"OK current: {doc['count']} robots derived from disk")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}  ({doc['count']} robots)")
    for name, r in sorted(doc["robots"].items()):
        mark = " ".join("✓" if r["provides_measured"].get(v) else "·"
                        for v in STANDARD_INTERFACE)
        print(f"  {name:12s} {r['coverage']:3d}%  {mark}  {r['verbs'] or 0:3d} verbs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
