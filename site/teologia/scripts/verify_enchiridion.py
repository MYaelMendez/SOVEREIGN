#!/usr/bin/env python3
"""Verify enchiridion: PDF contains æqr vector data + HTML integrity."""
from __future__ import annotations
import re, subprocess, shutil, zlib, sys
from pathlib import Path

TEO = Path(r"C:\æ\site\teologia")
HTML = TEO / "enchiridion.html"
PDF = TEO / "enchiridion.pdf"
TMP = Path(r"C:\Users\yaelm\AppData\Local\Temp\teo")
TMP.mkdir(parents=True, exist_ok=True)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# ---- 1. HTML integrity -----------------------------------------------------
html = HTML.read_text(encoding="utf-8")
print("=== HTML ===")
print("  bytes            :", len(html.encode('utf-8')))
print("  badge svg present:", html.count('class="aqr"'))
print("  download link    :", 'href="enchiridion.pdf"' in html)
m = re.search(r'id="hash">([a-f0-9]{16})', html)
print("  hash line        :", m.group(1) if m else "MISSING")
print("  sections (part)  :", html.count('class="part"'))
print("  prayers          :", html.count('class="prayer"'))
print("  psalms           :", html.count('class="psalm"'))
print("  unclosed divs    :", html.count("<div") - html.count("</div>"))

# ---- 2. Regenerate PDF from the CURRENT file -------------------------------
shutil.copy(HTML, TMP / "p.html")
subprocess.run([
    CHROME, "--headless", "--disable-gpu", "--no-sandbox",
    f"--print-to-pdf={TMP / 'p.pdf'}", "--no-pdf-header-footer",
    "--virtual-time-budget=8000",
    "file:///C:/Users/yaelm/AppData/Local/Temp/teo/p.html",
], capture_output=True, timeout=120)
shutil.copy(TMP / "p.pdf", PDF)

# ---- 3. PDF: does the QR vector data live inside? --------------------------
raw = PDF.read_bytes()
print("\n=== PDF ===")
print("  bytes            :", len(raw))
print("  header           :", raw[:8])
print("  pages            :", len(re.findall(rb"/Type\s*/Page[^s]", raw)))
print("  eof              :", raw.rstrip()[-5:])
rects = 0
streams = 0
for m in re.finditer(rb"stream\r?\n", raw):
    start = m.end()
    end = raw.find(b"endstream", start)
    if end == -1:
        continue
    blob = raw[start:end]
    try:
        data = zlib.decompress(blob)
    except Exception:
        continue
    streams += 1
    rects += len(re.findall(rb"\bre\b", data))
print("  streams decoded  :", streams)
print("  rect ops (re)    :", rects)
print("  -> QR vector in PDF:", "YES" if rects > 500 else "NO  (badge missing!)")
sys.exit(0 if rects > 500 else 3)
