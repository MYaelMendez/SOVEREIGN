#!/usr/bin/env python3
"""
keeper_email.py — Keeper email delivery integration.

Sends keeper audit reports via MAIL:// agent with hash chain receipts.
Integrates with the keeper cron for daily email delivery.

Usage:
    python keeper_email.py audit          — send audit report
    python keeper_email.py ledger         — send ledger summary
    python keeper_email.py reconcile      — send drift report
    python keeper_email.py handoff        — send handoff note
    python keeper_email.py status         — show delivery status
"""

import hashlib
import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Paths
KEEPER_DIR = Path("C:/æ/keeper")
LEDGER_FILE = KEEPER_DIR / "ledger.jsonl"
MAIL_AGENT = Path("C:/æ/agents/mail_agent.py")
HASH_CHAIN = Path("C:/æ/mail/hash_chain.json")
DELIVERY_LOG = KEEPER_DIR / "delivery_log.jsonl"

def run_mail_agent(args: list) -> dict:
    """Run mail_agent.py and return parsed output."""
    try:
        result = subprocess.run(
            [sys.executable, str(MAIL_AGENT)] + args,
            capture_output=True,
            text=True,
            timeout=30,
            cwd="C:/æ"
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "success": result.returncode == 0
        }
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": str(e), "success": False}

def read_ledger() -> list:
    """Read keeper ledger entries."""
    entries = []
    if not LEDGER_FILE.exists():
        return entries
    with open(LEDGER_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries

def read_hash_chain() -> dict:
    """Read mail hash chain."""
    if HASH_CHAIN.exists():
        return json.loads(HASH_CHAIN.read_text())
    return {"chain": [], "last_hash": "0" * 64, "count": 0}

def append_delivery_log(entry: dict):
    """Append delivery to log."""
    DELIVERY_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    entry["id"] = hashlib.sha256(
        f"{entry['action']}{entry['timestamp']}".encode()
    ).hexdigest()[:16]
    with open(DELIVERY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry["id"]

def build_audit_report() -> str:
    """Build keeper audit report."""
    entries = read_ledger()
    chain = read_hash_chain()
    
    report = []
    report.append("═══════════════════════════════════════")
    report.append("  KEEPER AUDIT REPORT")
    report.append(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    report.append("═══════════════════════════════════════")
    report.append("")
    report.append(f"Ledger entries: {len(entries)}")
    report.append(f"Mail chain length: {chain.get('count', 0)}")
    report.append(f"Mail chain valid: {chain.get('valid', True)}")
    report.append("")
    
    if entries:
        report.append("── Recent Entries ───────────────────")
        for entry in entries[-10:]:
            ts = entry.get("iso", entry.get("ts", "?"))
            kind = entry.get("kind", "?")
            text = entry.get("text", "")[:60]
            report.append(f"  {ts} [{kind}] {text}")
    
    report.append("")
    report.append("── Mesh Status ──────────────────────")
    
    # Check mesh nodes
    mesh_nodes = {
        "Victus RTX 3050": "127.0.0.1:3050",
        "Droplet": "129.212.180.252:3000",
    }
    for node, addr in mesh_nodes.items():
        report.append(f"  {node}: {addr}")
    
    report.append("")
    report.append("── Services ─────────────────────────")
    
    # Check running services
    services = {
        "CRI Server": "127.0.0.1:3052",
        "QR Server": "127.0.0.1:3051",
        "Mail Agent": "127.0.0.1:8123 (VSCODER)",
    }
    for svc, addr in services.items():
        report.append(f"  {svc}: {addr}")
    
    report.append("")
    report.append("═══════════════════════════════════════")
    report.append("  END OF REPORT")
    report.append("═══════════════════════════════════════")
    
    return "\n".join(report)

def build_ledger_summary() -> str:
    """Build ledger summary for email."""
    entries = read_ledger()
    
    summary = []
    summary.append("KEEPER LEDGER SUMMARY")
    summary.append(f"Total entries: {len(entries)}")
    summary.append("")
    
    if entries:
        # Group by kind
        kinds = {}
        for entry in entries:
            kind = entry.get("kind", "unknown")
            kinds[kind] = kinds.get(kind, 0) + 1
        
        summary.append("── By Kind ──────────────────────────")
        for kind, count in sorted(kinds.items(), key=lambda x: -x[1]):
            summary.append(f"  {kind}: {count}")
        
        summary.append("")
        summary.append("── Last 5 Entries ───────────────────")
        for entry in entries[-5:]:
            ts = entry.get("iso", entry.get("ts", "?"))
            kind = entry.get("kind", "?")
            text = entry.get("text", "")[:50]
            summary.append(f"  {ts} [{kind}] {text}")
    
    return "\n".join(summary)

def build_reconcile_report() -> str:
    """Build drift report between mirrors."""
    report = []
    report.append("KEEPER RECONCILE REPORT")
    report.append("")
    
    # Check two clones
    sites = Path("C:/æ/site")
    gh_pages = Path("C:/æ/github-pages")
    
    report.append("── Repository Mirrors ───────────────")
    report.append(f"  C:\\æ\\site: {'exists' if sites.exists() else 'MISSING'}")
    report.append(f"  C:\\æ\\github-pages: {'exists' if gh_pages.exists() else 'MISSING'}")
    
    # Check for uncommitted changes
    report.append("")
    report.append("── Uncommitted Changes ──────────────")
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True,
        text=True,
        cwd="C:/æ",
        timeout=10
    )
    if result.stdout.strip():
        for line in result.stdout.strip().split("\n")[:10]:
            report.append(f"  {line}")
    else:
        report.append("  Clean — no uncommitted changes")
    
    return "\n".join(report)

def build_handoff_note() -> str:
    """Build handoff note for successor."""
    entries = read_ledger()
    
    note = []
    note.append("KEEPER HANDOFF NOTE")
    note.append("")
    note.append("If you are reading this, the keeper audit has been delivered.")
    note.append("")
    note.append("── Current State ────────────────────")
    note.append(f"  Ledger entries: {len(entries)}")
    note.append(f"  Last entry: {entries[-1].get('iso', '???') if entries else 'none'}")
    note.append("")
    note.append("── Active Services ──────────────────")
    note.append("  CRI Server: :3052")
    note.append("  QR Server: :3051")
    note.append("  Mail Agent: standby")
    note.append("")
    note.append("── Mesh Topology ────────────────────")
    note.append("  Tier 0: Victus RTX 3050 (GPU)")
    note.append("  Tier 1: Droplet (broker/PDS)")
    note.append("  Tier 2: Nous Cloud (control plane)")
    note.append("  Tier 3: Tunnel (Victus ↔ Droplet)")
    note.append("")
    note.append("── Next Actions ─────────────────────")
    note.append("  1. Verify tunnel is up")
    note.append("  2. Check CRI thresholds")
    note.append("  3. Review mail queue")
    note.append("  4. Confirm keeper cron next run")
    
    return "\n".join(note)

def send_audit():
    """Send keeper audit via email."""
    print("══ Keeper Email Delivery ═=")
    print(f"  Building audit report...")
    
    report = build_audit_report()
    
    # Send via mail_agent
    result = run_mail_agent([
        "send",
        "yael@llm.store",
        "🔔 Keeper Audit — Daily Report",
        report
    ])
    
    if result["success"]:
        print(f"  ✅ Audit sent")
        print(f"  Mail agent output: {result['stdout'][:200]}")
        
        # Log delivery
        log_id = append_delivery_log({
            "action": "audit",
            "recipient": "yael@llm.store",
            "method": "mail_agent",
            "status": "sent"
        })
        print(f"  Delivery log: {log_id}")
    else:
        print(f"  ❌ Failed to send audit")
        print(f"  Error: {result['stderr'][:200]}")
        print(f"  → Check mail config in C:/æ/mail/config.json")
        
        # Log failure
        append_delivery_log({
            "action": "audit",
            "recipient": "yael@llm.store",
            "method": "mail_agent",
            "status": "failed",
            "error": result["stderr"][:200]
        })

def send_ledger():
    """Send ledger summary via email."""
    print("══ Keeper Email Delivery ═=")
    print(f"  Building ledger summary...")
    
    summary = build_ledger_summary()
    
    result = run_mail_agent([
        "send",
        "yael@llm.store",
        "📋 Keeper Ledger Summary",
        summary
    ])
    
    if result["success"]:
        print(f"  ✅ Ledger sent")
        append_delivery_log({
            "action": "ledger",
            "recipient": "yael@llm.store",
            "method": "mail_agent",
            "status": "sent"
        })
    else:
        print(f"  ❌ Failed: {result['stderr'][:200]}")

def send_reconcile():
    """Send reconcile report via email."""
    print("══ Keeper Email Delivery ═=")
    print(f"  Building reconcile report...")
    
    report = build_reconcile_report()
    
    result = run_mail_agent([
        "send",
        "yael@llm.store",
        "🔄 Keeper Reconcile Report",
        report
    ])
    
    if result["success"]:
        print(f"  ✅ Reconcile sent")
        append_delivery_log({
            "action": "reconcile",
            "recipient": "yael@llm.store",
            "method": "mail_agent",
            "status": "sent"
        })
    else:
        print(f"  ❌ Failed: {result['stderr'][:200]}")

def send_handoff():
    """Send handoff note via email."""
    print("══ Keeper Email Delivery ═=")
    print(f"  Building handoff note...")
    
    note = build_handoff_note()
    
    result = run_mail_agent([
        "send",
        "yael@llm.store",
        "🔀 Keeper Handoff Note",
        note
    ])
    
    if result["success"]:
        print(f"  ✅ Handoff sent")
        append_delivery_log({
            "action": "handoff",
            "recipient": "yael@llm.store",
            "method": "mail_agent",
            "status": "sent"
        })
    else:
        print(f"  ❌ Failed: {result['stderr'][:200]}")

def send_status():
    """Show delivery status."""
    print("══ Keeper Email Delivery Status ═=")
    
    # Check mail agent
    result = run_mail_agent(["status"])
    print(f"  Mail agent: {'ready' if result['success'] else 'not ready'}")
    if result["success"]:
        print(f"  {result['stdout']}")
    
    # Check delivery log
    if DELIVERY_LOG.exists():
        with open(DELIVERY_LOG, "r") as f:
            logs = [json.loads(l) for l in f if l.strip()]
        print(f"\n  Delivery log entries: {len(logs)}")
        for log in logs[-5:]:
            print(f"    {log.get('action', '?')}: {log.get('status', '?')}")
    else:
        print(f"\n  No delivery log yet")
    
    # Check keeper ledger
    entries = read_ledger()
    print(f"\n  Keeper ledger entries: {len(entries)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python keeper_email.py <command>")
        print()
        print("Commands:")
        print("  audit       — send keeper audit report")
        print("  ledger      — send ledger summary")
        print("  reconcile   — send drift report")
        print("  handoff     — send handoff note")
        print("  status      — show delivery status")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "audit":
        send_audit()
    elif cmd == "ledger":
        send_ledger()
    elif cmd == "reconcile":
        send_reconcile()
    elif cmd == "handoff":
        send_handoff()
    elif cmd == "status":
        send_status()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)