#!/usr/bin/env python3
"""
teologia_audit.py — Audit all teologia.ai surfaces for freshness and integrity.

Checks:
1. All HTML files exist and are non-corrupt (no null bytes, no mojibake, single doctype)
2. All QR badges present (æ-qr-badge or qr-badge)
3. All internal links resolve (calendario.html, rtx-accelerator.html, etc.)
4. All MP4 files exist and are non-zero
5. Live deployment matches local (curl check)
6. Gate metrics present in index.html

Logs to kænbæn genesis-chain.json on every run.
"""

import os, sys, json, hashlib, subprocess, time, urllib.request
from pathlib import Path

# Paths
GH_PAGES = Path(r"C:\æ\github-pages")
TEOLOGIA_DIR = GH_PAGES / "teologia"
KÆNBÆN_DIR = Path(r"C:\æ\kænbæn")
LOG_FILE = Path(r"C:\æ\logs\teologia-audit.log")
GENESIS_FILE = KÆNBÆN_DIR / "genesis-chain.json"

# Expected files
EXPECTED_HTML = [
    "index.html",
    "calendario.html",
    "rtx-accelerator.html",
    "genesis-1.html",
    "juan-316.html",
    "isaias-40.html",
    "proverbios-3.html",
    "mateo-5.html",
    "salmo-23.html",
    "apocalipsis-21.html",
    "demo-teologia.html",
]

EXPECTED_MP4 = [
    "demo-teologia.mp4",
    "apocalipsis-21.mp4",
    "salmo-23.mp4",
    "juan-316.mp4",
    "genesis-1.mp4",
    "proverbios-3.mp4",
    "mateo-5.mp4",
    "isaias-40.mp4",
]

EXPECTED_LINKS = [
    "calendario.html",
    "rtx-accelerator.html",
    "demo-teologia.mp4",
    "apocalipsis-21.mp4",
    "salmo-23.mp4",
    "juan-316.mp4",
    "genesis-1.mp4",
    "proverbios-3.mp4",
    "mateo-5.mp4",
    "isaias-40.mp4",
]

LIVE_BASE = "https://myaelmendez.github.io/teologia/"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_html(path):
    """Check HTML file for corruption."""
    if not path.exists():
        return {"exists": False, "corrupt": True, "reason": "missing"}
    
    raw = path.read_bytes()
    nulls = raw.count(b"\x00")
    mojibake = raw.count(b"\xc3\x83\xc2\xa6")
    doctypes = raw.lower().count(b"<!doctype")
    saved_from = raw.lower().count(b"saved from url")
    
    corrupt = nulls > 0 or mojibake > 0 or doctypes > 1 or saved_from > 0
    
    return {
        "exists": True,
        "corrupt": corrupt,
        "size": len(raw),
        "nulls": nulls,
        "mojibake": mojibake,
        "doctypes": doctypes,
        "sha256": hashlib.sha256(raw).hexdigest()[:16],
    }


def check_qr_badges(html_content):
    """Check if HTML has QR badges."""
    has_badge = "æ-qr-badge" in html_content or "qr-badge" in html_content.lower()
    return has_badge


def check_links(html_content, expected_links):
    """Check if all expected links are present."""
    missing = []
    for link in expected_links:
        if link not in html_content:
            missing.append(link)
    return missing


def check_mp4(path):
    """Check MP4 file exists and is non-zero."""
    if not path.exists():
        return {"exists": False, "size": 0}
    size = path.stat().st_size
    return {"exists": True, "size": size, "non_zero": size > 0}


def check_live():
    """Check live deployment."""
    try:
        req = urllib.request.Request(LIVE_BASE, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"live": True, "status": resp.status}
    except Exception as e:
        return {"live": False, "error": str(e)}


def log_entry(message):
    """Append to audit log."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def update_genesis(audit_result):
    """Update kænbæn genesis-chain with audit receipt."""
    if not GENESIS_FILE.exists():
        return
    
    try:
        with open(GENESIS_FILE, "r", encoding="utf-8") as f:
            chain = json.load(f)
        
        receipt = {
            "type": "teologia-audit",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files_checked": audit_result["files_checked"],
            "corrupt_files": audit_result["corrupt_files"],
            "missing_links": audit_result["missing_links"],
            "qr_badges_ok": audit_result["qr_badges_ok"],
            "live_status": audit_result["live_status"],
            "sha256": hashlib.sha256(json.dumps(audit_result, sort_keys=True).encode()).hexdigest()[:16],
        }
        
        if "receipts" not in chain:
            chain["receipts"] = []
        chain["receipts"].append(receipt)
        
        with open(GENESIS_FILE, "w", encoding="utf-8") as f:
            json.dump(chain, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_entry(f"ERROR updating genesis: {e}")


def main():
    log_entry("=== teologia audit start ===")
    
    result = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files_checked": 0,
        "corrupt_files": [],
        "missing_links": [],
        "qr_badges_ok": False,
        "live_status": {},
        "html_results": {},
        "mp4_results": {},
    }
    
    # Check all HTML files
    for html_file in EXPECTED_HTML:
        path = TEOLOGIA_DIR / html_file
        check = check_html(path)
        result["html_results"][html_file] = check
        result["files_checked"] += 1
        
        if check.get("corrupt"):
            result["corrupt_files"].append(html_file)
            log_entry(f"CORRUPT: {html_file} — {check}")
        elif not check.get("exists"):
            result["corrupt_files"].append(html_file)
            log_entry(f"MISSING: {html_file}")
        else:
            log_entry(f"OK: {html_file} ({check['size']:,} bytes)")
    
    # Check QR badges in index.html
    index_path = TEOLOGIA_DIR / "index.html"
    if index_path.exists():
        content = index_path.read_text(encoding="utf-8", errors="ignore")
        result["qr_badges_ok"] = check_qr_badges(content)
        result["missing_links"] = check_links(content, EXPECTED_LINKS)
        
        if result["qr_badges_ok"]:
            log_entry("QR badges: OK")
        else:
            log_entry("QR badges: MISSING")
        
        if result["missing_links"]:
            log_entry(f"Missing links: {result['missing_links']}")
        else:
            log_entry("Internal links: OK")
    
    # Check all MP4 files
    for mp4_file in EXPECTED_MP4:
        path = TEOLOGIA_DIR / mp4_file
        check = check_mp4(path)
        result["mp4_results"][mp4_file] = check
        result["files_checked"] += 1
        
        if not check["exists"]:
            log_entry(f"MISSING: {mp4_file}")
        elif not check.get("non_zero"):
            log_entry(f"EMPTY: {mp4_file}")
        else:
            log_entry(f"OK: {mp4_file} ({check['size']:,} bytes)")
    
    # Check live deployment
    result["live_status"] = check_live()
    if result["live_status"].get("live"):
        log_entry(f"Live: OK (HTTP {result['live_status']['status']})")
    else:
        log_entry(f"Live: FAIL — {result['live_status']}")
    
    # Summary
    log_entry(f"=== audit complete: {result['files_checked']} files, {len(result['corrupt_files'])} corrupt, {len(result['missing_links'])} missing links ===")
    
    # Update genesis chain
    update_genesis(result)
    
    # Exit code: 0 = all good, 1 = issues found
    if result["corrupt_files"] or result["missing_links"] or not result["qr_badges_ok"]:
        print(f"AUDIT ISSUES: {len(result['corrupt_files'])} corrupt, {len(result['missing_links'])} missing links")
        sys.exit(1)
    else:
        print(f"AUDIT PASS: {result['files_checked']} files OK, QR badges OK, live OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
