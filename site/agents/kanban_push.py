#!/usr/bin/env python3
"""
kanban_push.py — fleet-safe push to a shared repo, serialized through the kanban.

THE PROBLEM THIS SOLVES
-----------------------
Multiple agents share one clone of `MYaelMendez.github.io`. They each:
  1. `git add` / `git commit` on whatever branch the clone happens to be on
  2. `git push origin gh-pages`
  3. get rejected (non-fast-forward) because another agent pushed first
  4. retry, or worse, create a side branch and leave the commit stranded

Observed in one session: pushes hung 52 minutes, failed with exit 23, and one
commit landed on a branch called `widget-deploy` that nobody was watching.

The root cause is not the network. It is that **agents do not coordinate**. They
work from their own idea of what is true and discover the collision only at push
time.

THE FIX
-------
The kanban is the coordination substrate. A push is a unit of work, so it gets a
task, and the task is the lock:

    claim(task) → lock → fetch → rebase → push → record SHA → release

An exclusive lock (SQLite `BEGIN IMMEDIATE` on the kanban DB) serializes the
fetch/rebase/push window, so two agents cannot interleave and lose a commit. The
task records the resulting commit SHA, so the board — not a chat log — is the
record of what landed.

USAGE
-----
    # push under a task (creates + claims it if missing)
    python kanban_push.py push --task "deploy: viewport-os gate" --branch gh-pages

    # see who is holding the lock
    python kanban_push.py status

    # a stranded branch (a commit nobody is watching) — recover it
    python kanban_push.py rescue --branch widget-deploy --to gh-pages

WHY A LOCK AND NOT JUST RETRY
-----------------------------
Retry-on-reject works for a human pushing once. For N agents it is a thundering
herd: each retry re-fetches, re-rebases, and races again. The lock converts N
concurrent pushes into N sequential ones — O(N) work instead of O(N²) collisions.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import time

REPO = pathlib.Path(os.environ.get("FLEET_REPO", r"C:\æ\github-pages"))
KANBAN_DB = pathlib.Path(os.environ.get(
    "HERMES_KANBAN_DB",
    str(pathlib.Path(os.environ.get("LOCALAPPDATA", pathlib.Path.home()))
        / "hermes" / "kanban.db")))
LOCK_TIMEOUT = float(os.environ.get("FLEET_LOCK_TIMEOUT", "180"))


# ── git helpers ───────────────────────────────────────────────────────────────

def _git(*args, cwd=None, timeout=180) -> tuple[int, str]:
    cmd = ["git", "-c", "http.sslBackend=openssl", "-c", "http.version=HTTP/1.1",
           "-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=60"] + list(args)
    try:
        r = subprocess.run(cmd, cwd=str(cwd or REPO), capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s: git {' '.join(args)}"


def branch() -> str:
    _, out = _git("branch", "--show-current")
    return out.strip()


def head() -> str:
    _, out = _git("rev-parse", "HEAD")
    return out.strip()


def remote_head(remote="origin", br="gh-pages") -> str:
    _git("fetch", remote, br, "-q", timeout=120)
    _, out = _git("rev-parse", f"{remote}/{br}")
    return out.strip()


# ── the lock (the whole point) ────────────────────────────────────────────────

class KanbanLock:
    """An exclusive lock on the kanban DB, used to serialize the push window.

    `BEGIN IMMEDIATE` takes a RESERVED lock on the database file immediately, so
    two processes cannot both enter the critical section. We hold it across
    fetch → rebase → push. That is what makes N agents behave like a queue
    instead of a race.
    """

    def __init__(self, db: pathlib.Path, task_id: str, timeout: float = LOCK_TIMEOUT):
        self.db, self.task_id, self.timeout = db, task_id, timeout
        self.con = None
        self.acquired_at = None

    def __enter__(self):
        start = time.time()
        self.con = sqlite3.connect(str(self.db), timeout=self.timeout, isolation_level=None)
        self.con.execute("PRAGMA busy_timeout=%d" % int(self.timeout * 1000))
        while True:
            try:
                self.con.execute("BEGIN IMMEDIATE")
                break
            except sqlite3.OperationalError:
                if time.time() - start > self.timeout:
                    raise TimeoutError(f"could not acquire the fleet lock in {self.timeout}s")
                time.sleep(0.4)
        self.acquired_at = time.time()
        # record the holder so `status` can show it
        self._event("lock_acquired")
        return self

    def _event(self, kind: str, payload: dict | None = None):
        try:
            self.con.execute(
                "INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?,?,?,?)",
                (self.task_id, kind, json.dumps(payload or {}), int(time.time())))
        except sqlite3.Error:
            pass  # events are advisory; never fail the push over telemetry

    def record_push(self, sha: str, branch_name: str, detail: str = ""):
        """Record the landed commit ON THE LOCK'S OWN CONNECTION.

        This must use `self.con`, not a fresh connection: we hold a RESERVED lock
        on the DB, so a second connection would block until its busy_timeout and
        then fail with "database is locked". Writing through the lock's
        connection is the whole reason the lock is a context manager.
        """
        try:
            self.con.execute("UPDATE tasks SET branch_name = ? WHERE id = ?",
                             (branch_name, self.task_id))
            self.con.execute(
                "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?,?,?,?)",
                (self.task_id, "kanban_push",
                 f"pushed {sha[:12]} to {branch_name} {detail}".strip(), int(time.time())))
            self.con.execute(
                "INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?,?,?,?)",
                (self.task_id, "pushed",
                 json.dumps({"sha": sha, "branch": branch_name}), int(time.time())))
        except sqlite3.Error as e:
            print(f"  ! could not record the commit on {self.task_id}: {e}")

    def __exit__(self, *exc):
        try:
            self._event("lock_released")
            self.con.execute("COMMIT")
        except sqlite3.Error:
            pass
        finally:
            self.con.close()
        return False


# ── task helpers (in-process kanban, no subprocess) ───────────────────────────

def _kanban():
    for root in (pathlib.Path(r"C:\æ\hermes-pr-cuda"), pathlib.Path(r"C:\æ\hermes-fork")):
        if (root / "hermes_cli" / "kanban.py").exists():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            try:
                import hermes_cli.kanban as k
                return k
            except Exception:
                continue
    return None


def ensure_task(title: str, assignee: str | None = None) -> str:
    """Find a task by exact title, or create it. Returns the task id."""
    if not KANBAN_DB.exists():
        raise FileNotFoundError(f"no kanban at {KANBAN_DB} — run `kanban init`")
    con = sqlite3.connect(str(KANBAN_DB))
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT id FROM tasks WHERE title = ?", (title,)).fetchone()
    if row:
        con.close()
        return row["id"]
    con.close()

    k = _kanban()
    if k is None:
        raise RuntimeError("kanban module not importable — cannot create a task")
    out = k.run_slash(f'create "{title}"')
    # "Created t_abc123  (ready, assignee=-)"
    for tok in str(out).split():
        if tok.startswith("t_"):
            tid = tok.strip()
            if assignee:
                k.run_slash(f"assign {tid} {assignee}")
            return tid
    raise RuntimeError(f"could not parse a task id from: {out!r}")


# ── the operations ────────────────────────────────────────────────────────────

def cmd_push(args) -> int:
    title = args.task
    tid = ensure_task(title, args.assignee)
    print(f"  task   {tid}  ({title})")
    print(f"  repo   {REPO}")
    print(f"  branch {args.branch}")

    cur = branch()
    if cur != args.branch:
        print(f"  note   clone is on '{cur}', pushing its HEAD to '{args.branch}'")

    with KanbanLock(KANBAN_DB, tid) as lock:
        print("  lock   acquired — holding across fetch/rebase/push")

        rc, out = _git("fetch", "origin", args.branch, "-q", timeout=150)
        if rc != 0:
            print(f"  ✗ fetch failed: {out[:200]}")
            return 1

        local, remote = head(), remote_head()
        if local == remote:
            print(f"  = already in sync at {local[:12]}")
            return 0

        # is our HEAD ahead of remote (fast-forward) or diverged?
        rc_ff, _ = _git("merge-base", "--is-ancestor", f"origin/{args.branch}", "HEAD")
        if rc_ff == 0:
            print(f"  ff     {remote[:12]} → {local[:12]} (fast-forward, no rebase needed)")
        else:
            print("  rebase diverged — stashing, rebasing, restoring")
            _git("stash", "push", "-u", "-m", f"kanban-push-{tid}")
            rc, out = _git("pull", "--rebase", "origin", args.branch, timeout=180)
            if rc != 0:
                print(f"  ✗ rebase failed: {out[:300]}")
                _git("rebase", "--abort")
                _git("stash", "pop")
                return 1
            _git("stash", "pop")

        rc, out = _git("push", "origin", f"HEAD:{args.branch}", timeout=240)
        if rc != 0:
            print(f"  ✗ push failed: {out[:300]}")
            return 1

        sha = head()
        print(f"  ✓ pushed {sha[:12]} → {args.branch}")
        lock.record_push(sha, args.branch, args.detail or "")
    return 0


def cmd_status(args) -> int:
    print(f"  repo    {REPO}")
    print(f"  branch  {branch()}  (HEAD {head()[:12]})")
    try:
        print(f"  remote  {remote_head()[:12]}")
    except Exception as e:
        print(f"  remote  ? ({e})")
    print(f"  kanban  {KANBAN_DB}")

    # recent push events = who pushed what, in order
    if KANBAN_DB.exists():
        con = sqlite3.connect(str(KANBAN_DB))
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT e.created_at, e.task_id, e.payload, t.title "
            "FROM task_events e LEFT JOIN tasks t ON t.id = e.task_id "
            "WHERE e.kind = 'pushed' ORDER BY e.id DESC LIMIT 10").fetchall()
        if rows:
            print("\n  recent pushes (from the board):")
            for r in rows:
                try:
                    sha = json.loads(r["payload"]).get("sha", "?")[:12]
                except Exception:
                    sha = "?"
                when = time.strftime("%H:%M:%S", time.localtime(r["created_at"]))
                print(f"    {when}  {sha}  {r['task_id']}  {(r['title'] or '')[:40]}")
        else:
            print("\n  no pushes recorded on the board yet")
        con.close()
    return 0


def cmd_rescue(args) -> int:
    """Recover a stranded commit — one that landed on a branch nobody watches."""
    print(f"  rescuing '{args.branch}' → '{args.to}'")
    rc, out = _git("rev-parse", args.branch)
    if rc != 0:
        print(f"  ✗ no such branch: {args.branch}")
        return 1
    stranded = out.strip()
    print(f"  stranded HEAD {stranded[:12]}")

    tid = ensure_task(args.task or f"rescue: {args.branch} → {args.to}")
    with KanbanLock(KANBAN_DB, tid) as lock:
        _git("fetch", "origin", args.to, "-q", timeout=150)
        rc, _ = _git("merge-base", "--is-ancestor", f"origin/{args.to}", args.branch)
        if rc != 0:
            print(f"  ✗ '{args.branch}' is not ahead of origin/{args.to} — nothing to rescue")
            return 1
        rc, out = _git("push", "origin", f"{args.branch}:{args.to}", timeout=240)
        if rc != 0:
            print(f"  ✗ push failed: {out[:300]}")
            return 1
        print(f"  ✓ rescued {stranded[:12]} → {args.to}")
        lock.record_push(stranded, args.to, f"(rescued from {args.branch})")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="fleet-safe push, serialized through the kanban")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("push")
    p.add_argument("--task", required=True, help="the unit of work (created if missing)")
    p.add_argument("--branch", default="gh-pages")
    p.add_argument("--assignee", default=None)
    p.add_argument("--detail", default="")
    p.set_defaults(fn=cmd_push)

    s = sub.add_parser("status")
    s.set_defaults(fn=cmd_status)

    r = sub.add_parser("rescue")
    r.add_argument("--branch", required=True)
    r.add_argument("--to", default="gh-pages")
    r.add_argument("--task", default=None)
    r.set_defaults(fn=cmd_rescue)

    a = ap.parse_args(argv[1:])
    if not getattr(a, "fn", None):
        ap.print_help()
        return 1
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
