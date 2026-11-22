"""
sync_github_activity.py — derive a compact, honest activity snapshot.

Source: GitHub public REST events for MYaelMendez (no credential, no secret in
any output). The GitHub API is authoritative for the event stream; the page's
record is a DERIVED claim with a fetched_at timestamp, never hand-written.

Reads:  https://api.github.com/users/MYaelMendez/events?per_page=100
Writes: C:/æ/github-pages/github-activity.json  (schema ae/github-activity/1)

Run:  python sync_github_activity.py [--check]
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

USER = "MYaelMendez"
API = f"https://api.github.com/users/{USER}/events?per_page=100"
OUT = Path("C:/æ/github-pages/github-activity.json")
SCHEMA = "ae/github-activity/1"
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"}


def fetch() -> list:
    req = urllib.request.Request(API, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def derive(events: list) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    recent = []
    for e in events:
        try:
            ts = datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
        except (ValueError, KeyError):
            continue
        if ts >= cutoff:
            recent.append(e)

    by_type = Counter(e.get("type", "?") for e in recent)
    by_repo = Counter(e.get("repo", {}).get("name", "?") for e in recent)
    # newest first, de-duplicate by (type, repo, created_at) — API order is not sorted
    seen, timeline = set(), []
    for e in sorted(recent,
                    key=lambda x: x.get("created_at", ""), reverse=True):
        key = (e.get("type"), e.get("repo", {}).get("name"), e.get("created_at"))
        if key in seen:
            continue
        seen.add(key)
        event = {k: e.get(k) for k in ("type", "created_at")}
        event["repo"] = e.get("repo", {}).get("name")
        if e.get("payload", {}).get("commits"):
            event["commits"] = len(e["payload"]["commits"])
        timeline.append(event)
        if len(timeline) >= 12:
            break

    return {
        "schema": SCHEMA,
        "source": "GitHub REST public events (api.github.com/users/MYaelMendez/events)",
        "login": USER,
        "fetched_at": now.isoformat(),
        "window_days": 7,
        "events_in_window": len(recent),
        "events_fetched": len(events),
        "by_type": dict(by_type.most_common()),
        "by_repo": dict(by_repo.most_common(8)),
        "timeline": timeline,
        "note": ("Public events API returns at most 100 recent events and can lag; "
                 "counts are for the events returned, not a contribution total. "
                 "No credential is stored in this artifact."),
    }


def check(d: dict) -> bool:
    assert d["schema"] == SCHEMA
    assert d["events_in_window"] <= d["events_fetched"]
    assert sum(d["by_type"].values()) <= d["events_in_window"] + len(d["by_type"])
    assert d["login"] == USER
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify an existing snapshot")
    args = ap.parse_args()
    if args.check:
        d = json.loads(OUT.read_text(encoding="utf-8"))
        print("check:", "OK" if check(d) else "FAIL", d["fetched_at"])
        return
    d = derive(fetch())
    OUT.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    check(d)
    print(f"wrote {OUT} — {d['events_in_window']} events in 7d "
          f"({', '.join(f'{k}:{v}' for k, v in d['by_type'].items())})")


if __name__ == "__main__":
    main()
