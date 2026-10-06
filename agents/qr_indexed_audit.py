#!/usr/bin/env python3
"""QR-Indexed Code Mode: single-pass repo scan → QR envelope."""
import re, os, json, hashlib, base64, zlib
from pathlib import Path
from collections import Counter

ROOT = "C:/æ"
ROOTS = ["C:/æ/site", "C:/æ/agents", "C:/æ/vscoder", "C:/æ/hermes-fork/vscode-remote-use"]
PATTERNS = {
    "CRITICAL": [
        (r'<script type=["\']module["\']>', "ESM module script in HTML"),
        (r'from ["\']three/', "Three.js ESM import (needs global r147)"),
        (r'import \* as THREE', "ESM import * as THREE (needs window.THREE)"),
    ],
    "WARNING": [
        (r'^export ', "ES module export"),
        (r'from ["\']\./', "relative import"),
        (r'from ["\']\.\./', "parent relative import"),
    ],
}

findings = []
exts = {".html", ".js", ".mjs", ".ts", ".jsx", ".tsx"}
skip_dirs = {"node_modules", ".git", "__pycache__", "vendor", "dist", "build",
             "atproto-private-client", "gpu-mcp", "hermes-mobile-app",
             "threejs-curriculum", "hermes-fork", "cuda-mcp2-demo",
             ".vscode", "fonts", "extensions"}
file_count = 0

for root in ROOTS:
    if not os.path.exists(root):
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for f in filenames:
            ext = os.path.splitext(f)[1]
            if ext not in exts:
                continue
            file_count += 1
            fp = os.path.join(dirpath, f)
            try:
                lines = Path(fp).read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                for sev, pats in PATTERNS.items():
                    for regex, desc in pats:
                        if re.search(regex, line):
                            findings.append({
                                "file": str(Path(fp).relative_to(ROOT)),
                                "line": i, "pattern": desc, "severity": sev,
                                "snippet": line.strip()[:80],
                            })

scan_hash = hashlib.sha256(json.dumps(findings, sort_keys=True).encode()).hexdigest()
summary = {
    "scheme": "code-mode://audit",
    "sha256": scan_hash[:32],
    "total_findings": len(findings),
    "files_scanned": file_count,
    "by_severity": dict(Counter(f["severity"] for f in findings)),
    "by_type": dict(Counter(f["pattern"] for f in findings)),
}

qr_data = f"ae://audit/{scan_hash[:24]}"
print(json.dumps(summary, indent=2))
print()
print(f"QR: {qr_data}")
print(f"\nTop findings (showing 15/{len(findings)}):")
for f in sorted(findings, key=lambda x: 0 if x["severity"] == "CRITICAL" else 1)[:15]:
    short = f["file"].replace("\\", "/").split("/")[-1]
    print(f"  [{f['severity'][:4]}] {short}:{f['line']} - {f['pattern']}")
