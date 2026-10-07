#!/usr/bin/env python3
"""
MAIL:// — Agentic Electronic Engineering Mail
Agentic email processing with hash chain receipts.

Integrates with:
- ae-as-skill (sovereign stack)
- keeper:// (custodian bot, ledger)
- cri:// (economic index alerts)
- vscoder:// (engineering studio)

Usage:
    python mail_agent.py status
    python mail_agent.py inbox
    python mail_agent.py triage
    python mail_agent.py reply <email_id> <response>
    python mail_agent.py send <to> <subject> <body>
    python mail_agent.py alert <threshold> <message>
"""

import imaplib
import smtplib
import ssl
import json
import hashlib
import os
import sys
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from dataclasses import dataclass, asdict
from typing import Optional
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────

MAIL_DIR = Path("C:/æ/mail")
LEDGER_FILE = MAIL_DIR / "ledger.json"
HASH_CHAIN_FILE = MAIL_DIR / "hash_chain.json"
CONFIG_FILE = MAIL_DIR / "config.json"

@dataclass
class MailConfig:
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    email: str = ""
    display_name: str = "VSCODER Agent"
    imap_user: str = ""
    imap_password: str = ""
    smtp_user: str = ""
    smtp_password: str = ""
    enabled: bool = False

@dataclass
class MailReceipt:
    email_id: str
    action: str  # read, triage, reply, send, alert
    timestamp: str
    hash: str
    previous_hash: str
    status: str  # pending, confirmed, failed
    evidence: dict = None

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = {}

# ─── Hash Chain ──────────────────────────────────────────────────

class HashChain:
    """Immutable hash chain for mail receipts."""

    def __init__(self, chain_file: Path):
        self.chain_file = chain_file
        self.chain = self._load()

    def _load(self) -> list:
        if self.chain_file.exists():
            data = json.loads(self.chain_file.read_text())
            return data.get("chain", [])
        return []

    def _save(self):
        self.chain_file.parent.mkdir(parents=True, exist_ok=True)
        self.chain_file.write_text(json.dumps({
            "chain": self.chain,
            "last_hash": self.last_hash(),
            "count": len(self.chain)
        }, indent=2))

    def last_hash(self) -> str:
        if self.chain:
            return self.chain[-1]["hash"]
        return "0" * 64  # genesis

    def append(self, receipt: MailReceipt) -> str:
        receipt.previous_hash = self.last_hash()
        receipt.hash = self._hash(receipt)
        self.chain.append(asdict(receipt))
        self._save()
        return receipt.hash

    def _hash(self, receipt: MailReceipt) -> str:
        data = f"{receipt.email_id}{receipt.action}{receipt.timestamp}{receipt.previous_hash}"
        return hashlib.sha256(data.encode()).hexdigest()

    def verify(self) -> bool:
        """Verify the entire chain integrity."""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current["previous_hash"] != previous["hash"]:
                return False
            # Recompute hash
            rc = MailReceipt(
                email_id=current["email_id"],
                action=current["action"],
                timestamp=current["timestamp"],
                hash="",
                previous_hash=current["previous_hash"],
                status=current["status"],
                evidence=current.get("evidence", {})
            )
            expected = HashChain._hash_static(rc)
            if current["hash"] != expected:
                return False
        return True

    @staticmethod
    def _hash_static(receipt: MailReceipt) -> str:
        data = f"{receipt.email_id}{receipt.action}{receipt.timestamp}{receipt.previous_hash}"
        return hashlib.sha256(data.encode()).hexdigest()

# ─── Ledger ──────────────────────────────────────────────────────

class MailLedger:
    """Append-only ledger for mail actions."""

    def __init__(self, ledger_file: Path):
        self.ledger_file = ledger_file
        self.entries = self._load()

    def _load(self) -> list:
        if self.ledger_file.exists():
            data = json.loads(self.ledger_file.read_text())
            return data.get("entries", [])
        return []

    def _save(self):
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_file.write_text(json.dumps({
            "entries": self.entries,
            "count": len(self.entries)
        }, indent=2))

    def append(self, entry: dict):
        entry["id"] = hashlib.sha256(
            f"{entry['timestamp']}{entry['action']}{entry.get('email_id', '')}".encode()
        ).hexdigest()[:16]
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.entries.append(entry)
        self._save()
        return entry["id"]

# ─── Email Client ────────────────────────────────────────────────

class MailClient:
    """IMAP/SMTP client for agentic mail processing."""

    def __init__(self, config: MailConfig):
        self.config = config
        self.imap = None
        self.smtp = None

    def connect_imap(self):
        """Connect to IMAP server with TLS."""
        context = ssl.create_default_context()
        self.imap = imaplib.IMAP4_SSL(
            self.config.imap_host,
            self.config.imap_port,
            ssl_context=context
        )
        self.imap.login(self.config.imap_user, self.config.imap_password)
        return True

    def disconnect_imap(self):
        if self.imap:
            self.imap.logout()
            self.imap = None

    def connect_smtp(self):
        """Connect to SMTP server with STARTTLS."""
        self.smtp = smtplib.SMTP(
            self.config.smtp_host,
            self.config.smtp_port
        )
        self.smtp.starttls(context=ssl.create_default_context())
        self.smtp.login(self.config.smtp_user, self.config.smtp_password)
        return True

    def disconnect_smtp(self):
        if self.smtp:
            self.smtp.quit()
            self.smtp = None

    def list_folders(self) -> list:
        """List mail folders."""
        if not self.imap:
            self.connect_imap()
        status, folders = self.imap.list()
        if status == "OK":
            return [f.decode().split(' "/" ')[-1] for f in folders]
        return []

    def select_folder(self, folder: str = "INBOX"):
        """Select a mail folder."""
        if not self.imap:
            self.connect_imap()
        status, data = self.imap.select(f'"{folder}"')
        return status == "OK", int(data[0]) if status == "OK" else 0

    def list_emails(self, folder: str = "INBOX", limit: int = 20) -> list:
        """List emails in a folder."""
        if not self.imap:
            self.connect_imap()
        status, _ = self.select_folder(folder)
        if not status:
            return []

        status, data = self.imap.search(None, "ALL")
        if status != "OK":
            return []

        ids = data[0].split()[-limit:]
        emails = []
        for eid in ids:
            status, msg_data = self.imap.fetch(eid, "(BODY.PEEK[HEADER])")
            if status == "OK":
                raw = msg_data[0][1].decode("utf-8", errors="replace")
                emails.append(self._parse_header(raw, eid.decode()))
        return emails

    def _parse_header(self, raw: str, eid: str) -> dict:
        """Parse email headers."""
        headers = {}
        for line in raw.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                headers[key.strip().lower()] = val.strip()
        return {
            "id": eid,
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "message_id": headers.get("message-id", ""),
        }

    def read_email(self, email_id: str) -> dict:
        """Read full email content."""
        if not self.imap:
            self.connect_imap()
        status, data = self.imap.fetch(email_id.encode(), "(RFC822)")
        if status != "OK":
            return {"error": "not found"}
        raw = data[0][1].decode("utf-8", errors="replace")
        return {"id": email_id, "raw": raw}

    def send_email(self, to: str, subject: str, body: str, html: str = None) -> str:
        """Send an email."""
        if not self.smtp:
            self.connect_smtp()

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self.config.display_name} <{self.config.email}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")

        msg.attach(MIMEText(body, "plain"))
        if html:
            msg.attach(MIMEText(html, "html"))

        self.smtp.sendmail(self.config.email, [to], msg.as_string())
        return hashlib.sha256(f"{to}{subject}{body}".encode()).hexdigest()[:16]

# ─── Triage Engine ───────────────────────────────────────────────

class MailTriage:
    """Agentic inbox triage with classification."""

    DISPOSITIONS = {
        "urgent": ["deadline", "blocker", "security", "money", "executive", "critical", "urgent"],
        "reply": ["question", "request", "need", "can you", "please", "review"],
        "action": ["schedule", "pay", "file", "update", "submit", "confirm"],
        "waiting": ["follow up", "next step", "when", "later", "waiting"],
        "reference": ["info", "information", "update", "notice", "announcement"],
        "noise": ["newsletter", "unsubscribe", "promo", "spam", "marketing"],
    }

    def __init__(self, ledger: MailLedger, chain: HashChain):
        self.ledger = ledger
        self.chain = chain

    def classify(self, email: dict) -> str:
        """Classify email by disposition."""
        subject = email.get("subject", "").lower()
        body_preview = email.get("preview", "").lower()
        text = f"{subject} {body_preview}"

        scores = {}
        for disposition, keywords in self.DISPOSITIONS.items():
            scores[disposition] = sum(1 for kw in keywords if kw in text)

        if max(scores.values()) == 0:
            return "reference"
        return max(scores, key=scores.get)

    def triage_inbox(self, emails: list) -> list:
        """Triage a list of emails."""
        results = []
        for email in emails:
            disposition = self.classify(email)
            entry = {
                "email_id": email["id"],
                "disposition": disposition,
                "from": email["from"],
                "subject": email["subject"],
                "date": email["date"],
            }
            entry_id = self.ledger.append({
                "action": "triage",
                "email_id": email["id"],
                "disposition": disposition,
            })
            receipt = MailReceipt(
                email_id=email["id"],
                action="triage",
                timestamp=datetime.now(timezone.utc).isoformat(),
                hash="",
                previous_hash="",
                status="confirmed",
                evidence={"disposition": disposition, "ledger_id": entry_id}
            )
            self.chain.append(receipt)
            results.append(entry)
        return results

# ─── Alert System ────────────────────────────────────────────────

class MailAlerts:
    """Threshold-based alerts (CRI, hardware, mesh)."""

    def __init__(self, client: MailClient, ledger: MailLedger, chain: HashChain):
        self.client = client
        self.ledger = ledger
        self.chain = chain

    def check_cri_threshold(self, cri_score: float, threshold: float = 70.0):
        """Alert if CRI crosses threshold."""
        if cri_score >= threshold:
            return self.send_alert(
                "CRI Threshold Alert",
                f"CRI score {cri_score} exceeds threshold {threshold}"
            )
        return None

    def send_alert(self, subject: str, message: str) -> str:
        """Send an alert email."""
        receipt_id = self.client.send_email(
            self.config.email,
            f"⚠️ {subject}",
            message
        )
        entry_id = self.ledger.append({
            "action": "alert",
            "subject": subject,
            "message": message[:100],
        })
        receipt = MailReceipt(
            email_id=receipt_id,
            action="alert",
            timestamp=datetime.now(timezone.utc).isoformat(),
            hash="",
            previous_hash="",
            status="confirmed",
            evidence={"subject": subject, "ledger_id": entry_id}
        )
        self.chain.append(receipt)
        return receipt_id

# ─── CLI ─────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("MAIL:// Agentic Electronic Engineering Mail")
        print()
        print("Commands:")
        print("  status              — show config + chain integrity")
        print("  inbox               — list inbox emails")
        print("  triage              — triage inbox with classification")
        print("  read <id>           — read email")
        print("  send <to> <subj> <body> — send email")
        print("  alert <threshold>   — send CRI threshold alert")
        print("  verify              — verify hash chain integrity")
        sys.exit(1)

    cmd = sys.argv[1]

    # Load config
    config = MailConfig()
    if CONFIG_FILE.exists():
        cfg = json.loads(CONFIG_FILE.read_text())
        for k, v in cfg.items():
            setattr(config, k, v)

    # Initialize components
    ledger = MailLedger(LEDGER_FILE)
    chain = HashChain(HASH_CHAIN_FILE)
    client = MailClient(config)
    triage = MailTriage(ledger, chain)
    alerts = MailAlerts(client, ledger, chain)

    if cmd == "status":
        print(f"MAIL:// Status")
        print(f"  Configured: {config.enabled}")
        print(f"  Email: {config.email}")
        print(f"  Ledger entries: {len(ledger.entries)}")
        print(f"  Chain length: {len(chain.chain)}")
        print(f"  Chain valid: {chain.verify()}")
        print(f"  Last hash: {chain.last_hash()[:16]}...")

    elif cmd == "inbox":
        if not config.enabled:
            print("MAIL:// not configured — set config first")
            sys.exit(1)
        emails = client.list_emails()
        for e in emails:
            print(f"  {e['id']}: {e['from']} — {e['subject']}")

    elif cmd == "triage":
        if not config.enabled:
            print("MAIL:// not configured")
            sys.exit(1)
        emails = client.list_emails()
        results = triage.triage_inbox(emails)
        for r in results:
            print(f"  {r['disposition']:10s} {r['from'][:30]:30s} {r['subject'][:40]}")
        print(f"\n  {len(results)} emails triaged")

    elif cmd == "read":
        if len(sys.argv) < 3:
            print("Usage: mail_agent.py read <email_id>")
            sys.exit(1)
        email = client.read_email(sys.argv[2])
        print(json.dumps(email, indent=2)[:2000])

    elif cmd == "send":
        if len(sys.argv) < 5:
            print("Usage: mail_agent.py send <to> <subject> <body>")
            sys.exit(1)
        receipt = client.send_email(sys.argv[2], sys.argv[3], sys.argv[4])
        print(f"Sent: {receipt}")
        entry_id = ledger.append({"action": "send", "to": sys.argv[2], "subject": sys.argv[3]})
        r = MailReceipt(
            email_id=receipt,
            action="send",
            timestamp=datetime.now(timezone.utc).isoformat(),
            hash="", previous_hash="",
            status="confirmed",
            evidence={"ledger_id": entry_id}
        )
        chain.append(r)
        print(f"Ledger: {entry_id}, Chain valid: {chain.verify()}")

    elif cmd == "alert":
        threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 70.0
        receipt = alerts.check_cri_threshold(62.5, threshold)
        print(f"Alert sent: {receipt}")

    elif cmd == "verify":
        valid = chain.verify()
        print(f"Hash chain valid: {valid}")
        print(f"Chain length: {len(chain.chain)}")
        if not valid:
            for i in range(1, len(chain.chain)):
                curr = chain.chain[i]
                prev = chain.chain[i-1]
                if curr["previous_hash"] != prev["hash"]:
                    print(f"  BREAK at index {i}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()