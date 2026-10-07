#!/usr/bin/env python3
"""
væult_email.py — Email-to-vault pipeline.

Watches an inbox for emails with subject `[væult] KEY`, extracts the secret
from the body, encrypts it, and stores it in the vault. Marks the email as
processed (moves to a `væult-processed` folder or deletes it).

Usage:
    python væult_email.py watch          # continuous watch (cron-friendly)
    python væult_email.py check          # one-shot check
    python væult_email.py send <TO> <KEY> <VALUE>  # send a secret via email

Email format:
    Subject: [vault] KEY
    Body:    the secret value (first non-empty line)

Security:
    - The secret is encrypted with AES-256-GCM before storage
    - The email is moved to a processed folder after import
    - The passphrase comes from VAEULT_PASSPHRASE env var
    - Raw values are never printed to stdout
"""
from __future__ import annotations

import imaplib
import json
import os
import pathlib
import smtplib
import sys
import time
from email.mime.text import MIMEText
from email.header import decode_header
from typing import Optional

# ── config ────────────────────────────────────────────────────────────────────

VAULT_PATH = pathlib.Path(os.environ.get(
    "VAEULT_PATH", r"C:\æ\secrets\privateclient\privateclient.væult"))
VAEULT_MODULE = pathlib.Path(os.environ.get("VAEULT_MODULE", r"C:\æ\væult\væult.py"))

# IMAP config (set via env or config file)
IMAP_HOST = os.environ.get("VAEULT_IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.environ.get("VAEULT_IMAP_PORT", "993"))
IMAP_USER = os.environ.get("VAEULT_IMAP_USER", "")
IMAP_PASS = os.environ.get("VAEULT_IMAP_PASS", "")
IMAP_FOLDER = os.environ.get("VAEULT_IMAP_FOLDER", "INBOX")
PROCESSED_FOLDER = os.environ.get("VAEULT_PROCESSED_FOLDER", "væult-processed")

# SMTP config
SMTP_HOST = os.environ.get("VAEULT_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("VAEULT_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("VAEULT_SMTP_USER", IMAP_USER)
SMTP_PASS = os.environ.get("VAEULT_SMTP_PASS", IMAP_PASS)

POLL_INTERVAL = 60  # seconds between checks in watch mode


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_vault_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_vaeult_email", str(VAEULT_MODULE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _unlock_vault(mod):
    passphrase = os.environ.get("VAEULT_PASSPHRASE")
    if not passphrase:
        raise RuntimeError("VAEULT_PASSPHRASE not set")
    doc = mod.load_raw(VAULT_PATH)
    salt = mod._b64d(doc["salt"])
    kdf = doc.get("kdf", "scrypt")
    if kdf == "pbkdf2":
        key = mod.derive_key_pbkdf2(passphrase, salt, doc.get("iterations", 600000))
    else:
        key = mod.derive_key(passphrase, salt, doc.get("n", mod.KDF_N),
                             doc.get("r", mod.KDF_R), doc.get("p", mod.KDF_P))
    chk = doc.get("check")
    if chk:
        try:
            mod.open_entry(key, "__check__", chk)
        except Exception:
            raise RuntimeError("wrong passphrase")
    return key, doc


def _extract_secret(body: str) -> Optional[str]:
    """Extract the first non-empty line from the email body."""
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith(">"):
            return line
    return None


def _decode_subject(subject: str) -> str:
    parts = decode_header(subject)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


# ── IMAP ──────────────────────────────────────────────────────────────────────

def _connect_imap() -> imaplib.IMAP4_SSL:
    if not IMAP_USER or not IMAP_PASS:
        raise RuntimeError("VAEULT_IMAP_USER / VAEULT_IMAP_PASS not set")
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(IMAP_USER, IMAP_PASS)
    return mail


def _ensure_processed_folder(mail: imaplib.IMAP4_SSL):
    """Create the processed folder if it doesn't exist."""
    typ, folders = mail.list()
    if folders:
        folder_names = [f.decode().split(' "/"')[-1].strip('"') for f in folders if f]
        if PROCESSED_FOLDER not in folder_names:
            mail.create(PROCESSED_FOLDER)


def check_inbox() -> list[dict]:
    """Check inbox for [væult] emails. Returns list of {key, value, uid}."""
    if not VAULT_PATH.exists():
        return []

    mod = _load_vault_module()
    key, doc = _unlock_vault(mod)

    mail = _connect_imap()
    try:
        _ensure_processed_folder(mail)
        mail.select(IMAP_FOLDER)

        typ, data = mail.search(None, "UNSEEN")
        if not data or not data[0]:
            return []

        results = []
        for uid in data[0].split():
            typ, msg_data = mail.fetch(uid, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")

            import email
            msg = email.message_from_string(raw)
            subject = _decode_subject(msg.get("Subject", ""))

            if not subject.startswith("[væult]"):
                continue

            key_name = subject[len("[væult]"):].strip()
            if not key_name:
                continue

            # Extract body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

            secret = _extract_secret(body)
            if not secret:
                continue

            # Encrypt and store
            blob = mod.seal(key, key_name, secret)
            doc["entries"][key_name] = blob
            doc["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            mod.save_raw(VAULT_PATH, doc)

            # Move to processed folder
            mail.copy(uid, PROCESSED_FOLDER)
            mail.store(uid, "+FLAGS", "\\Deleted")

            results.append({"key": key_name, "uid": uid.decode()})

        mail.expunge()
        return results
    finally:
        mail.logout()


def watch():
    """Continuous watch loop."""
    print(f"væult email watcher — checking {IMAP_FOLDER} every {POLL_INTERVAL}s")
    print(f"  vault: {VAULT_PATH}")
    print(f"  processed folder: {PROCESSED_FOLDER}")
    while True:
        try:
            results = check_inbox()
            for r in results:
                print(f"  ✓ imported '{r['key']}' from email (uid {r['uid']})")
        except Exception as e:
            print(f"  ✗ error: {e}")
        time.sleep(POLL_INTERVAL)


# ── SMTP ──────────────────────────────────────────────────────────────────────

def send_secret(to: str, key: str, value: str):
    """Send a secret via email with [væult] subject."""
    if not SMTP_USER or not SMTP_PASS:
        raise RuntimeError("VAEULT_SMTP_USER / VAEULT_SMTP_PASS not set")

    msg = MIMEText(value)
    msg["Subject"] = f"[væult] {key}"
    msg["From"] = SMTP_USER
    msg["To"] = to

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

    print(f"  ✓ sent '{key}' to {to}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "check":
        results = check_inbox()
        if results:
            for r in results:
                print(f"  ✓ imported '{r['key']}' from email")
        else:
            print("  no new [væult] emails")

    elif cmd == "watch":
        watch()

    elif cmd == "send":
        if len(sys.argv) < 5:
            print("usage: væult_email.py send <TO> <KEY> <VALUE>")
            return
        send_secret(sys.argv[2], sys.argv[3], sys.argv[4])

    else:
        print(f"unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
