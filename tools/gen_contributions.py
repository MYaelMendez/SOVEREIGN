#!/usr/bin/env python3
"""gen_contributions.py — derive the GitHub contribution calendar from GraphQL.

Same discipline as gen_qr_inventory.py / gen_filmmemory_status.py: the catalog
is DERIVED, never hand-written. Source of truth is GitHub's GraphQL
`contributionsCollection` for the canonical operator account.

    python tools/gen_contributions.py            # write + mirror
    python tools/gen_contributions.py --check    # exit 1 if stale

SECURITY: the gh CLI token is used only as an auth mechanism on this machine.
NO token, header, cookie, or credential is ever written to the surface, a
receipt, a log, or a path. The emitted JSON contains ONLY public calendar data.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:/æ")
OUT = ROOT / "github-pages/contributions.json"
MIRROR = ROOT / "site/contributions.json"
LOGIN = "MYaelMendez"
QUERY = ('query{user(login:"' + LOGIN + '"){contributionsCollection{'
         'contributionCalendar{totalContributions,weeks{contributionDays{'
         'date,contributionCount}}}}}}')


def fetch() -> dict:
    env = os.environ.copy()
    r = subprocess.run(['gh', 'api', 'graphql', '-f', f'query={QUERY}'],
                       capture_output=True, text=True, timeout=120,
                       encoding='utf-8', errors='replace', env=env)
    if r.returncode != 0:
        raise RuntimeError(f"gh graphql failed: {(r.stderr or r.stdout)[:200]}")
    return json.loads(r.stdout)['data']['user']['contributionsCollection']['contributionCalendar']


def derive() -> dict:
    cal = fetch()
    days = [d for w in cal['weeks'] for d in w['contributionDays']]
    active = [d for d in days if d['contributionCount'] > 0]
    per_month: dict[str, int] = {}
    for d in days:
        m = d['date'][:7]
        per_month[m] = per_month.get(m, 0) + d['contributionCount']
    return {
        "schema": "ae/github-contributions/1",
        "source": "GitHub GraphQL contributionsCollection (public calendar data)",
        "login": LOGIN,
        "derived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_contributions": cal['totalContributions'],
        "weeks": len(cal['weeks']),
        "days": len(days),
        "active_days": len(active),
        "max_per_day": max((d['contributionCount'] for d in days), default=0),
        "first_day": days[0]['date'] if days else None,
        "last_day": days[-1]['date'] if days else None,
        "per_month": dict(sorted(per_month.items())),
        "calendar": [{"d": d['date'], "n": d['contributionCount']} for d in days],
        "note": "Derived, never hand-written. No credential is stored in this surface.",
    }


def render(d: dict) -> str:
    return json.dumps(d, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="derive contributions.json from GitHub GraphQL")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = render(derive())
    if a.check:
        if not OUT.exists():
            print(f"MISSING: {OUT}", file=sys.stderr); return 1
        # ignore derived_at: re-deriving changes the timestamp every run
        cur = json.loads(OUT.read_text(encoding="utf-8"))
        new = json.loads(text)
        keys = [k for k in new if k != "derived_at"]
        if any(cur.get(k) != new[k] for k in keys):
            print(f"STALE: {OUT.name} differs from GitHub — regenerate", file=sys.stderr)
            return 1
        print(f"OK: {OUT.name} is current (total={new['total_contributions']})")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    MIRROR.write_text(text, encoding="utf-8")
    print(f"  mirrored -> {MIRROR}")
    d = json.loads(text)
    print(f"  total={d['total_contributions']} active={d['active_days']} weeks={d['weeks']} max/day={d['max_per_day']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
