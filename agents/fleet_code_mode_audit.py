#!/usr/bin/env python3
"""
Code Mode: Fleet audit of ESM module usage across HTML, JS, and TS files.

Single execution replaces ~15 sequential MCP file-read + grep calls.
Pre-bound globals in sandbox: re, json, os, sys, storage, keeper.
Uses standard library only (re, os, sys, json).

Scans for:
  <script type="module">   → CRITICAL  (ESM module in HTML)
  <script type="importmap"> → CRITICAL  (import maps in HTML)
  import .*                 → WARNING   (ESM imports)
  export .*                 → WARNING   (ESM exports)
  from 'three/'             → WARNING   (Three.js ESM imports)
  from './'                  → WARNING   (relative imports without resolution)
  from '../'                 → WARNING   (relative imports without resolution)

Usage:
  python fleet_code_mode_audit.py <dir>

Output: JSON array of {file, line, pattern, severity}
"""

import re, json, sys, os

# ── Configuration ──────────────────────────────────────────────────────────

# File extensions to scan for ESM patterns
EXTENSIONS = ('.html', '.htm', '.js', '.ts', '.mjs', '.mts', '.jsx', '.tsx')

# Directories to prune during traversal
SKIP_DIRS = frozenset({'.git', 'node_modules', '__pycache__', '.venv',
                        '.venv-gpu', 'venv', 'env', '.venv3', 'dist', 'build'})

# Pattern definitions: (compiled_regex, severity)
# CRITICAL = ESM module in HTML (script type=module or importmap)
# WARNING  = ESM imports/exports and relative module specifiers
PATTERNS = [
    # ── CRITICAL: ESM in HTML ──────────────────────────────────────────
    (re.compile(r'<script[^>]*type=["\']module["\'][^>]*>'),  'CRITICAL'),
    (re.compile(r'<script[^>]*type=["\']importmap["\'][^>]*>'), 'CRITICAL'),
    # ── WARNING: ESM imports ───────────────────────────────────────────
    (re.compile(r'import\s+'),                                  'WARNING'),
    (re.compile(r'export\s+'),                                  'WARNING'),
    # ── WARNING: module specifiers ─────────────────────────────────────
    (re.compile(r"from\s+['\"]three/"),                        'WARNING'),
    (re.compile(r"from\s+['\"]\./"),                           'WARNING'),
    (re.compile(r"from\s+['\"]\.\./"),                         'WARNING'),
]

# Patterns list for reporting (count of distinct regex patterns)
# ── Scan logic ────────────────────────────────────────────────────────────

def scan_file(file_path):
    """
    Scan a single file for ESM module patterns.
    Returns a list of dicts: {file, line, pattern, severity}.
    """
    findings = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except (IOError, OSError):
        return findings

    for lineno, line in enumerate(lines, 1):
        for pattern, severity in PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append({
                    'file': file_path,
                    'line': lineno,
                    'pattern': match.group(0),
                    'severity': severity,
                })
    return findings


def scan_directory(target_dir):
    """
    Walk a directory tree (pruning SKIP_DIRS) and scan all matching
    files for ESM patterns. Returns (findings_list, files_scanned_count).
    """
    all_findings = []
    files_scanned = 0

    for root, dirs, files in os.walk(target_dir):
        # Prune skipped directories in-place so os.walk doesn't descend into them
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for filename in sorted(files):
            if filename.endswith(EXTENSIONS):
                file_path = os.path.join(root, filename)
                files_scanned += 1
                all_findings.extend(scan_file(file_path))

    return all_findings, files_scanned


# ── Main entry point ──────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: python fleet_code_mode_audit.py <dir>'}))
        sys.exit(1)

    target_dir = sys.argv[1]

    if not os.path.isdir(target_dir):
        print(json.dumps({'error': f'Directory not found: {target_dir}'}))
        sys.exit(1)

    findings, files_scanned = scan_directory(target_dir)

    # Primary output: JSON array of {file, line, pattern, severity}
    print(json.dumps(findings, indent=2))

    # Audit trail — Code Mode keeper (available in sandbox, no-op standalone)
    try:
        keeper = globals().get('keeper')
        if keeper is None:
            keeper = globals().get('\xc3\xa6')  # æ namespace
        if keeper is not None:
            audit_fn = getattr(keeper, 'audit', None)
            if audit_fn is not None:
                audit_fn(
                    'fleet_code_mode_audit',
                    f'Scanned {files_scanned} files for ESM patterns, found {len(findings)}',
                    evidence=json.dumps({
                        'files_scanned': files_scanned,
                        'findings_count': len(findings),
                    }),
                )
    except Exception:
        pass

    # Summary to stderr — keeps stdout as pure JSON
    print(f'— Scanned {files_scanned} files, found {len(findings)} ESM patterns —',
          file=sys.stderr)


if __name__ == '__main__':
    main()
