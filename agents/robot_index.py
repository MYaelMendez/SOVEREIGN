#!/usr/bin/env python3
"""robot index — one development contract, every robot measured against it.

The rule this encodes: whatever we build for ONE robot, we provide for ALL.
So the index is not a list of robots; it is the STANDARD INTERFACE every robot
is expected to implement, with a measured verdict per robot.

    robot://<robot>/<verb>     the address
    status                     present? transports? live? ledger tail?
    verbs                      the verb table, hashed (the policy IS the verbs)
    plan <command>             a plan, never an act (address ≠ permission)
    sim <command>              the simulation trace, receipted
    exec <command>             hardware — requires approval, stays dry-run
    receipt                    the ledger, hash-chained
    ledger                     the ledger tail, verifiable

Generated from robot://doctor + the assets on disk. Never hand-edited.
"""
from __future__ import annotations

import argparse
import hashlib
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

# Which dialect verb satisfies each standard verb. Declared, not inferred:
# the dialects name things differently, and a guessed mapping is a false claim.
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
}


def _verb_table(mod) -> list[str]:
    try:
        return sorted(rp._verb_table(mod))
    except Exception:
        return []


def build() -> dict:
    doc = rp.dispatch("robot://doctor")
    robots = doc.get("robots", {})
    out_robots = {}
    for name, meta in robots.items():
        try:
            mod = rp._load(meta["module"])
            verbs = _verb_table(mod)
        except Exception:
            mod, verbs = None, []
        classes = meta.get("classes") or {}
        covered = [v for v in STANDARD_INTERFACE
                   if v == "status" or (v in verbs or v in classes
                                        or (v == "receipt" and bool(meta.get("ledger")))
                                        or (v == "ledger" and bool(meta.get("ledger"))))]
        provides = PROVIDES.get(name, {})
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
            "provides": {v: provides.get(v) for v in STANDARD_INTERFACE},
            "coverage": round(100 * sum(1 for v in STANDARD_INTERFACE if provides.get(v))
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
                "coverage": 0, "reason": "mesh only — no dialect, no policy",
            }

    roster = sorted(out_robots)
    return {
        "schema": "robot-index/1",
        "authority": rp.AUTHORITY,
        "generated": rp.datetime.now(rp.timezone.utc).isoformat(timespec="seconds"),
        "standard_interface": STANDARD_INTERFACE,
        "categories": CATEGORIES,
        "roster": roster,
        "count": len(roster),
        "robots": out_robots,
        "unregistered_dialects": doc.get("unregistered_dialects"),
        "meshes": meshes,
        "coverage_kind": "declared — PROVIDES maps each standard verb to a dialect "
                        "verb by hand; the dialects expose no machine-readable "
                        "'I implement X' flag, so this is a claim to verify, not a "
                        "measurement",
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
        mark = " ".join("✓" if r["provides"].get(v) else "·" for v in STANDARD_INTERFACE)
        print(f"  {name:12s} {r['coverage']:3d}%  {mark}  {r['verbs'] or 0:3d} verbs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
