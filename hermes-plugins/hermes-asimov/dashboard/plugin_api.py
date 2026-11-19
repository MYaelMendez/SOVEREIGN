"""hermes-asimov dashboard backend — read-only status/cast/ledger + plan.

The desktop pane calls these via ctx.rest(). Rules honored here:
  * menlo is imported LAZILY inside handlers — a missing SDK never breaks
    the plugin import.
  * A refusal is a structured result {ok: false, refused: true, reason: ...},
    never an exception.
  * No authority is ever granted. /plan dispatches through the existing
    protocol engine (scripts/asimov_protocol.py), which never connects to
    a robot. The engine is wrapped, never reimplemented.
"""
import asyncio
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

PLUGIN_DIR = Path(__file__).resolve().parent.parent
CAST_FILE = PLUGIN_DIR / "cast.json"
ENGINE = PLUGIN_DIR / "scripts" / "asimov_protocol.py"
CAST_SCHEMA = "hermes-asimov/cast/1"
PROTOCOL_VERSION = "asimov-protocol/1"
LEDGER_FILES = (
    "tiny-voca-receipts.jsonl",
    "ae-receipts.jsonl",
    "asimov-protocol.jsonl",
)
GENESIS_PREV = {"0" * 64, "GENESIS"}


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))


def _refused(reason: str) -> dict:
    return {"ok": False, "refused": True, "reason": reason}


def _read_cast_doc():
    """Return (cast_list, error). Read-only; schema-checked."""
    try:
        doc = json.loads(CAST_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"cast file missing: {CAST_FILE}"
    except Exception as exc:
        return None, f"cast file unreadable: {exc}"
    if not isinstance(doc, dict) or doc.get("schema") != CAST_SCHEMA:
        return None, f"unexpected cast schema (want {CAST_SCHEMA})"
    cast = doc.get("cast")
    if not isinstance(cast, list):
        return None, "cast.json has no cast array"
    return cast, None


def _ledger_report(path: Path) -> dict:
    report = {
        "file": path.name,
        "present": path.exists(),
        "entries": 0,
        "chain_verified": False,
        "head": None,
        "actions": {},
    }
    if not report["present"]:
        return report
    entries = []
    parse_error = None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    except Exception as exc:
        parse_error = str(exc)
    report["entries"] = len(entries)
    report["actions"] = dict(Counter(
        e.get("action", "?") for e in entries if isinstance(e, dict)
    ))
    if parse_error is not None:
        report["chain_error"] = parse_error
        return report
    if not entries:
        report["chain_verified"] = True  # empty chain is trivially intact
        return report
    verified = True
    prev_hash = None
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            verified = False
            break
        prev = entry.get("prev")
        if i == 0:
            if prev not in GENESIS_PREV:
                verified = False
                break
        elif prev != prev_hash:
            verified = False
            break
        prev_hash = entry.get("hash")
    report["chain_verified"] = verified
    report["head"] = entries[-1].get("hash") if isinstance(entries[-1], dict) else None
    return report


@router.get("/status")
async def status():
    # Lazy: a missing menlo-sdk must not break the plugin.
    try:
        import importlib.metadata as md
        sdk_version = md.version("menlo-sdk")
    except Exception:
        sdk_version = "not installed"
    cast, cast_err = _read_cast_doc()
    return {
        "ok": True,
        "sdk_version": sdk_version,
        "robot_configured": bool(
            os.environ.get("MENLO_ROBOT") or os.environ.get("MENLO_UDP_HOST")
        ),
        "live": os.environ.get("HERMES_AE_SDK_LIVE") == "1",
        "protocol": PROTOCOL_VERSION,
        "cast_size": len(cast) if cast is not None else 0,
        "cast_error": cast_err,
        "authority": "HUMAN://ROOT",
        "note": "An address is not a permission. This pane grants nothing.",
    }


@router.get("/cast")
async def cast():
    cast_list, err = _read_cast_doc()
    if err is not None:
        return _refused(err)
    return cast_list


@router.get("/ledger")
async def ledger():
    home = _hermes_home()
    return {
        "ok": True,
        "hermes_home": str(home),
        "ledgers": [_ledger_report(home / name) for name in LEDGER_FILES],
    }


class PlanBody(BaseModel):
    verb: str = ""


def _run_engine(raw: str) -> dict:
    """Wrap the protocol engine via subprocess. Never reimplement it."""
    if not ENGINE.exists():
        return _refused(f"protocol engine missing: {ENGINE}")
    py = os.environ.get("HERMES_AE_PYTHON", sys.executable)
    env = dict(os.environ)
    # A contaminated PYTHONPATH breaks the child interpreter on this host.
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    env["HERMES_HOME"] = str(_hermes_home())
    try:
        proc = subprocess.run(
            [py, str(ENGINE), raw],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            env=env,
        )
    except Exception as exc:
        return _refused(f"engine invocation failed: {exc}")
    try:
        result = json.loads(proc.stdout)
    except Exception:
        return _refused(
            "engine returned no JSON: "
            + ((proc.stderr or proc.stdout or "no output").strip()[-400:])
        )
    if isinstance(result, dict):
        return result
    return _refused("engine returned a non-object result")


@router.post("/plan")
async def plan(body: PlanBody):
    verb = (body.verb or "").strip()
    if not verb:
        return _refused("verb required")
    if any(ch.isspace() for ch in verb):
        return _refused("verb must be a single token")
    # asimov://plan is policy-evaluated and NEVER connects to a robot.
    result = await asyncio.to_thread(_run_engine, f"asimov://plan {verb}")
    if result.get("refused") or result.get("success") is False:
        return {
            "ok": False,
            "refused": True,
            "reason": result.get("reason") or result.get("error") or "engine refused",
            "engine": result,
        }
    result["ok"] = True
    return result
