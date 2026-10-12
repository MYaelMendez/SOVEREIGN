#!/usr/bin/env python3
"""
chain_propagate.py — make every session aware of the chain.

THE PROBLEM
-----------
SOUL.md reaches a session when its system prompt is BUILT. But a continuing
session does not rebuild — it reuses the exact prompt stored in SQLite, so the
Anthropic cache prefix stays stable:

    run_agent.py:
        if stored_prompt:
            self._cached_system_prompt = stored_prompt     # reuse, do not rebuild

That is correct for cost. The consequence is that a session started before the
chain was added keeps the OLD prompt forever — across restarts, across
`/new`, for the life of that session row.

So "all our sessions are aware of the chain" is not achieved by editing SOUL.md.
It needs three things:

    1. DETECT   which stored prompts predate the chain
    2. DECIDE   is staleness acceptable? (cache stability vs. awareness)
    3. PROPAGATE the ones that must be brought current

WHAT THIS TOOL DOES
-------------------
`status`  — every session, whether its stored prompt carries the chain
`stale`   — just the ones that do not
`plan`    — what a refresh would cost (which sessions, how much cache loss)
`refresh` — rebuild the prompt for the sessions that must know

THE HONEST TRADE
----------------
Refreshing a session's prompt invalidates its cache prefix: the next turn pays
full input price instead of the cached rate. So this does NOT blindly refresh
everything. A session that will never touch the chain does not need it; a
session that will, does. The default is to refresh only sessions that are
ACTIVE (recent) or explicitly named.

USAGE
    python chain_propagate.py status
    python chain_propagate.py stale
    python chain_propagate.py plan
    python chain_propagate.py refresh --active-within 7d
    python chain_propagate.py refresh --session <id>
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sqlite3
import sys
import time

HERMES_HOME = pathlib.Path(os.environ.get(
    "HERMES_HOME",
    str(pathlib.Path(os.environ.get("LOCALAPPDATA", pathlib.Path.home())) / "hermes")))

# Where the session DB lives. Profiles each have their own.
def _dbs() -> list[pathlib.Path]:
    """Every DB that actually has a `sessions` table with a system_prompt column.

    Discovered, not guessed: state.db is the live session store (1189 rows),
    while other *.db files have unrelated schemas. Hardcoding a filename would
    silently scan the wrong file.
    """
    out = []
    for p in sorted(HERMES_HOME.glob("*.db")):
        try:
            con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            tabs = {r[0] for r in con.execute(
                "SELECT name FROM main.sqlite_master WHERE type='table'")}
            if "sessions" in tabs:
                cols = {r[1] for r in con.execute("PRAGMA main.table_info(sessions)")}
                if "system_prompt" in cols:
                    out.append(p)
            con.close()
        except Exception:
            continue
    prof = HERMES_HOME / "profiles"
    if prof.is_dir():
        for d in prof.iterdir():
            for p in sorted(d.glob("*.db")):
                try:
                    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
                    tabs = {r[0] for r in con.execute(
                        "SELECT name FROM main.sqlite_master WHERE type='table'")}
                    if "sessions" in tabs:
                        cols = {r[1] for r in con.execute("PRAGMA main.table_info(sessions)")}
                        if "system_prompt" in cols:
                            out.append(p)
                    con.close()
                except Exception:
                    continue
    return out


# The markers that prove a prompt knows the chain. Any ONE is enough — a prompt
# built by an older SOUL.md may carry only the earliest.
MARKERS = ["væult_chain.py", "væult://chain", "Claim before you act",
           "NEVER MOVE A SECRET", "RULES OF THE æ:// CHAIN"]


def knows_chain(prompt: str | None) -> tuple[bool, list[str]]:
    if not prompt:
        return False, []
    found = [m for m in MARKERS if m in prompt]
    return bool(found), found


def _open(db: pathlib.Path):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def scan(db: pathlib.Path | None = None) -> dict:
    """Every session across every DB, with its chain awareness."""
    dbs = [db] if db else _dbs()
    rows = []
    for d in dbs:
        try:
            con = _open(d)
            cols = {r[1] for r in con.execute("PRAGMA main.table_info(sessions)")}
            if "system_prompt" not in cols:
                con.close()
                continue
            want = [c for c in ("id", "system_prompt", "started_at", "message_count")
                    if c in cols]
            sel = "SELECT " + ", ".join(f"main.sessions.{c}" for c in want) + " FROM main.sessions"
            for r in con.execute(sel):
                prompt = r["system_prompt"]
                ok, found = knows_chain(prompt)
                rows.append({
                    "db": str(d),
                    "id": r["id"] if "id" in cols else "-",
                    "started_at": r["started_at"] if "started_at" in cols else None,
                    "messages": r["message_count"] if "message_count" in cols else None,
                    "has_prompt": bool(prompt),
                    "prompt_chars": len(prompt or ""),
                    "knows_chain": ok,
                    "markers": found,
                })
            con.close()
        except Exception as e:
            rows.append({"db": str(d), "id": "-", "error": f"{type(e).__name__}: {e}"})
    return {"dbs": [str(x) for x in dbs], "sessions": rows}


def summarise(scan_result: dict) -> dict:
    s = [r for r in scan_result["sessions"] if "error" not in r]
    aware = [r for r in s if r["knows_chain"]]
    stale = [r for r in s if not r["knows_chain"]]
    return {
        "total": len(s), "aware": len(aware), "stale": len(stale),
        "no_prompt": len([r for r in s if not r["has_prompt"]]),
        "stale_ids": [r["id"] for r in stale],
    }


def age_days(started_at: float | None) -> float | None:
    if not started_at:
        return None
    return (time.time() - float(started_at)) / 86400.0


def plan(within_days: float | None = None) -> dict:
    """Which sessions would a refresh touch, and what does it cost?"""
    r = scan()
    s = [x for x in r["sessions"] if "error" not in x]
    stale = [x for x in s if not x["knows_chain"]]
    if within_days is not None:
        stale = [x for x in stale
                 if (age_days(x["started_at"]) or 1e9) <= within_days]
    chars = sum(x["prompt_chars"] for x in stale)
    return {
        "would_refresh": len(stale),
        "ids": [x["id"] for x in stale],
        "prompt_chars_total": chars,
        "cache_note": (
            "each refresh invalidates that session's cache prefix: the next turn "
            "pays full input price once, then re-caches"),
    }


def refresh(session_ids: list[str] | None = None,
            within_days: float | None = None, db: pathlib.Path | None = None,
            dry: bool = True) -> dict:
    """Rebuild the stored prompt for the named (or selected) sessions.

    A refresh does NOT rewrite the prompt by hand — it clears the stored value
    so the next turn rebuilds from the current SOUL.md/AGENTS.md. Clearing is
    the honest operation: it lets the real builder produce the real prompt,
    rather than this tool guessing at its content.
    """
    dbs = [db] if db else _dbs()
    targets = set(session_ids or [])
    if within_days is not None and not targets:
        p = plan(within_days)
        targets = set(p["ids"])

    touched = []
    for d in dbs:
        try:
            con = sqlite3.connect(str(d), timeout=10)
            con.row_factory = sqlite3.Row
            cols = {r[1] for r in con.execute("PRAGMA main.table_info(sessions)")}
            if "system_prompt" not in cols:
                con.close()
                continue
            for r in con.execute("SELECT id, system_prompt FROM main.sessions"):
                sid = r["id"]
                ok, _ = knows_chain(r["system_prompt"])
                if ok:
                    continue
                if targets and sid not in targets:
                    continue
                if dry:
                    touched.append({"id": sid, "db": str(d), "dry": True})
                    continue
                # clear so the next turn rebuilds from current context files
                con.execute("UPDATE main.sessions SET system_prompt = NULL WHERE id = ?", (sid,))
                touched.append({"id": sid, "db": str(d), "cleared": True})
            if not dry:
                con.commit()
            con.close()
        except Exception as e:
            touched.append({"error": f"{d}: {type(e).__name__}: {e}"})
    return {"dry": dry, "touched": touched, "count": len(touched)}


def main(argv):
    ap = argparse.ArgumentParser(description="make every session aware of the chain")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    sub.add_parser("stale")
    p = sub.add_parser("plan"); p.add_argument("--active-within", default=None)
    r = sub.add_parser("refresh")
    r.add_argument("--session", action="append", default=None)
    r.add_argument("--active-within", default=None)
    r.add_argument("--apply", action="store_true",
                   help="actually clear (default is a dry run)")
    a = ap.parse_args(argv[1:])

    if a.cmd == "status":
        res = scan(); s = summarise(res)
        print(f"SESSIONS — {s['aware']}/{s['total']} aware of the chain\n")
        for db in res["dbs"]:
            print(f"  db: {db}")
        print()
        for row in res["sessions"][:40]:
            if "error" in row:
                print(f"  ! {row['db']}: {row['error']}"); continue
            mark = "✓" if row["knows_chain"] else "·"
            age = age_days(row["started_at"])
            when = f"{age:.1f}d ago" if age is not None else "?"
            print(f"  {mark} {row['id'][:26]:28s} {when:10s} "
                  f"{row['messages'] or 0:5d} msgs  "
                  f"{'chain' if row['knows_chain'] else 'STALE'}")
        if s["stale"]:
            print(f"\n  {s['stale']} session(s) predate the chain.")
            print(f"  They reuse a stored prompt, so they will not see it until refreshed.")
        return 0

    if a.cmd == "stale":
        s = summarise(scan())
        for i in s["stale_ids"]:
            print(i)
        return 0

    def _days(x):
        if not x:
            return None
        x = x.strip().lower()
        return float(x[:-1]) if x.endswith("d") else float(x)

    if a.cmd == "plan":
        p = plan(_days(a.active_within))
        print(f"  would refresh: {p['would_refresh']} session(s)")
        for i in p["ids"][:20]:
            print(f"    {i}")
        print(f"\n  {p['cache_note']}")
        return 0

    if a.cmd == "refresh":
        res = refresh(a.session, _days(a.active_within), dry=not a.apply)
        mode = "DRY RUN" if res["dry"] else "APPLIED"
        print(f"  {mode}: {res['count']} session(s)")
        for t in res["touched"][:20]:
            if "error" in t:
                print(f"    ! {t['error']}"); continue
            print(f"    {t['id']}")
        if res["dry"]:
            print("\n  re-run with --apply to clear them.")
            print("  a cleared session rebuilds its prompt on the next turn,")
            print("  picking up the current SOUL.md — at the cost of one")
            print("  uncached turn.")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
