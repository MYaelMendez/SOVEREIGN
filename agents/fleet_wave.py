#!/usr/bin/env python3
"""
fleet_wave.py — fleet wave batch system for coordinated multi-agent deployment.

A wave is a group of related tasks that must all complete before the next wave starts.
Within a wave, tasks can be worked on in parallel by different agents.

The system uses the kanban DB for state tracking and the kanban lock for serialization.

Usage:
    python fleet_wave.py create --wave "deploy-tower" --tasks "task1,task2,task3" --branch gh-pages
    python fleet_wave.py status
    python fleet_wave.py claim --wave "deploy-tower" --task "task1" --agent "agent-1"
    python fleet_wave.py complete --wave "deploy-tower" --task "task1" --agent "agent-1" --sha abc123
    python fleet_wave.py deploy --wave "deploy-tower"
    python fleet_wave.py list
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

KANBAN_DB = Path(__file__).parent / "kanban.db"

def get_db():
    KANBAN_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(KANBAN_DB))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS waves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            branch TEXT NOT NULL DEFAULT 'gh-pages',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS wave_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wave_id INTEGER NOT NULL,
            task_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            agent TEXT,
            claimed_at TEXT,
            completed_at TEXT,
            commit_sha TEXT,
            FOREIGN KEY (wave_id) REFERENCES waves(id),
            UNIQUE(wave_id, task_name)
        );

        CREATE TABLE IF NOT EXISTS wave_locks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wave_id INTEGER NOT NULL,
            agent TEXT NOT NULL,
            locked_at TEXT NOT NULL,
            FOREIGN KEY (wave_id) REFERENCES waves(id)
        );
    """)
    conn.commit()
    conn.close()

def create_wave(name, tasks, branch='gh-pages'):
    init_db()
    conn = get_db()
    now = datetime.utcnow().isoformat()

    existing = conn.execute("SELECT id FROM waves WHERE name = ?", (name,)).fetchone()
    if existing:
        print(f"✗ Wave '{name}' already exists")
        return False

    cursor = conn.execute(
        "INSERT INTO waves (name, branch, status, created_at) VALUES (?, ?, 'pending', ?)",
        (name, branch, now)
    )
    wave_id = cursor.lastrowid

    for task in tasks:
        conn.execute(
            "INSERT INTO wave_tasks (wave_id, task_name, status) VALUES (?, ?, 'pending')",
            (wave_id, task)
        )

    conn.commit()
    conn.close()
    print(f"✓ Created wave '{name}' with {len(tasks)} tasks on branch '{branch}'")
    return True

def get_wave_status(wave_name):
    conn = get_db()
    wave = conn.execute("SELECT * FROM waves WHERE name = ?", (wave_name,)).fetchone()
    if not wave:
        print(f"✗ Wave '{wave_name}' not found")
        return None

    tasks = conn.execute(
        "SELECT * FROM wave_tasks WHERE wave_id = ? ORDER BY id",
        (wave['id'],)
    ).fetchall()

    conn.close()
    return {'wave': wave, 'tasks': tasks}

def claim_task(wave_name, task_name, agent):
    conn = get_db()
    wave = conn.execute("SELECT * FROM waves WHERE name = ?", (wave_name,)).fetchone()
    if not wave:
        print(f"✗ Wave '{wave_name}' not found")
        return False

    task = conn.execute(
        "SELECT * FROM wave_tasks WHERE wave_id = ? AND task_name = ?",
        (wave['id'], task_name)
    ).fetchone()

    if not task:
        print(f"✗ Task '{task_name}' not found in wave '{wave_name}'")
        return False

    if task['status'] != 'pending':
        print(f"✗ Task '{task_name}' is already {task['status']}")
        return False

    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE wave_tasks SET status = 'claimed', agent = ?, claimed_at = ? WHERE id = ?",
        (agent, now, task['id'])
    )
    conn.commit()
    conn.close()
    print(f"✓ Agent '{agent}' claimed task '{task_name}' in wave '{wave_name}'")
    return True

def complete_task(wave_name, task_name, agent, commit_sha=None):
    conn = get_db()
    wave = conn.execute("SELECT * FROM waves WHERE name = ?", (wave_name,)).fetchone()
    if not wave:
        print(f"✗ Wave '{wave_name}' not found")
        return False

    task = conn.execute(
        "SELECT * FROM wave_tasks WHERE wave_id = ? AND task_name = ?",
        (wave['id'], task_name)
    ).fetchone()

    if not task:
        print(f"✗ Task '{task_name}' not found in wave '{wave_name}'")
        return False

    if task['status'] == 'complete':
        print(f"✗ Task '{task_name}' is already complete")
        return False

    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE wave_tasks SET status = 'complete', completed_at = ?, commit_sha = ? WHERE id = ?",
        (now, commit_sha, task['id'])
    )
    conn.commit()
    conn.close()
    print(f"✓ Agent '{agent}' completed task '{task_name}' in wave '{wave_name}'")

    check_wave_complete(wave_name)
    return True

def check_wave_complete(wave_name):
    conn = get_db()
    wave = conn.execute("SELECT * FROM waves WHERE name = ?", (wave_name,)).fetchone()
    if not wave:
        return False

    tasks = conn.execute(
        "SELECT * FROM wave_tasks WHERE wave_id = ?",
        (wave['id'],)
    ).fetchall()

    all_complete = all(t['status'] == 'complete' for t in tasks)

    if all_complete and wave['status'] != 'complete':
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE waves SET status = 'complete', completed_at = ? WHERE id = ?",
            (now, wave['id'])
        )
        conn.commit()
        print(f"✓ Wave '{wave_name}' is complete!")

    conn.close()
    return all_complete

def deploy_wave(wave_name):
    conn = get_db()
    wave = conn.execute("SELECT * FROM waves WHERE name = ?", (wave_name,)).fetchone()
    if not wave:
        print(f"✗ Wave '{wave_name}' not found")
        return False

    if wave['status'] != 'complete':
        print(f"✗ Wave '{wave_name}' is not complete (status: {wave['status']})")
        return False

    tasks = conn.execute(
        "SELECT * FROM wave_tasks WHERE wave_id = ? AND commit_sha IS NOT NULL",
        (wave['id'],)
    ).fetchall()

    conn.close()

    if not tasks:
        print(f"✗ No tasks with commit SHAs in wave '{wave_name}'")
        return False

    for task in tasks:
        print(f"  Deploying {task['task_name']} (SHA: {task['commit_sha'][:12]})...")
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "kanban_push.py"),
             "push", "--task", f"wave:{wave_name}:{task['task_name']}",
             "--branch", wave['branch']],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  ✗ Deploy failed: {result.stderr}")
            return False
        print(f"  ✓ Deployed {task['task_name']}")

    print(f"✓ Wave '{wave_name}' deployed successfully!")
    return True

def list_waves():
    init_db()
    conn = get_db()
    waves = conn.execute("SELECT * FROM waves ORDER BY created_at DESC").fetchall()

    if not waves:
        print("No waves found")
        return

    for wave in waves:
        tasks = conn.execute(
            "SELECT * FROM wave_tasks WHERE wave_id = ?",
            (wave['id'],)
        ).fetchall()

        total = len(tasks)
        complete = sum(1 for t in tasks if t['status'] == 'complete')
        claimed = sum(1 for t in tasks if t['status'] == 'claimed')
        pending = sum(1 for t in tasks if t['status'] == 'pending')

        print(f"\n  {wave['name']} [{wave['status']}]")
        print(f"    Branch: {wave['branch']}")
        print(f"    Tasks: {complete}/{total} complete, {claimed} claimed, {pending} pending")
        print(f"    Created: {wave['created_at']}")

        for task in tasks:
            status_icon = "✓" if task['status'] == 'complete' else "○" if task['status'] == 'pending' else "◐"
            agent_info = f" ({task['agent']})" if task['agent'] else ""
            sha_info = f" [{task['commit_sha'][:12]}]" if task['commit_sha'] else ""
            print(f"      {status_icon} {task['task_name']}{agent_info}{sha_info}")

    conn.close()

def main(argv):
    parser = argparse.ArgumentParser(description="Fleet wave batch system")
    sub = parser.add_subparsers(dest="cmd")

    c = sub.add_parser("create")
    c.add_argument("--wave", required=True)
    c.add_argument("--tasks", required=True, help="Comma-separated task names")
    c.add_argument("--branch", default="gh-pages")

    s = sub.add_parser("status")
    s.add_argument("--wave", default=None)

    cl = sub.add_parser("claim")
    cl.add_argument("--wave", required=True)
    cl.add_argument("--task", required=True)
    cl.add_argument("--agent", required=True)

    co = sub.add_parser("complete")
    co.add_argument("--wave", required=True)
    co.add_argument("--task", required=True)
    co.add_argument("--agent", required=True)
    co.add_argument("--sha", default=None)

    d = sub.add_parser("deploy")
    d.add_argument("--wave", required=True)

    l = sub.add_parser("list")

    args = parser.parse_args(argv[1:])

    if args.cmd == "create":
        tasks = [t.strip() for t in args.tasks.split(",")]
        return 0 if create_wave(args.wave, tasks, args.branch) else 1
    elif args.cmd == "status":
        if args.wave:
            status = get_wave_status(args.wave)
            if status:
                print(json.dumps(status, indent=2, default=str))
        else:
            list_waves()
        return 0
    elif args.cmd == "claim":
        return 0 if claim_task(args.wave, args.task, args.agent) else 1
    elif args.cmd == "complete":
        return 0 if complete_task(args.wave, args.task, args.agent, args.sha) else 1
    elif args.cmd == "deploy":
        return 0 if deploy_wave(args.wave) else 1
    elif args.cmd == "list":
        list_waves()
        return 0
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
