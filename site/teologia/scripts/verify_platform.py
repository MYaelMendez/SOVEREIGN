#!/usr/bin/env python3
"""Generate index.pdf from index.html and verify the platform."""
import subprocess
import shutil
import hashlib
import re
import zlib
from pathlib import Path

ROOT = Path(r"C:\æ\site\teologia")
INDEX = ROOT / "index.html"
PDF = ROOT / "index.pdf"
TMP = Path(r"C:\Users\yaelm\AppData\Local\Temp\teo")
TMP.mkdir(parents=True, exist_ok=True)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# Copy to ASCII path
shutil.copy(INDEX, TMP / "index.html")

# Generate PDF
subprocess.run([
    CHROME, "--headless", "--disable-gpu", "--no-sandbox",
    f"--print-to-pdf={TMP / 'index.pdf'}", "--no-pdf-header-footer",
    "--virtual-time-budget=8000",
    "file:///C:/Users/yaelm/AppData/Local/Temp/teo/index.html",
], capture_output=True, timeout=120)
shutil.copy(TMP / "index.pdf", PDF)

raw = PDF.read_bytes()
print("=== index.pdf ===")
print("  bytes:", len(raw))
print("  header:", raw[:8])
print("  pages:", len(re.findall(rb"/Type\s*/Page[^s]", raw)))
print("  eof:", raw.rstrip()[-5:])

# QR vector check
rects = 0
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
    rects += len(re.findall(rb"\bre\b", data))
print("  rect ops (re):", rects)
print("  -> QR vector in PDF:", "YES" if rects > 500 else "NO")
print()

# Verify index.html integrity
html = INDEX.read_text(encoding="utf-8")
print("=== index.html ===")
print("  bytes:", len(html.encode("utf-8")))
print("  badge svg:", html.count('class="aqr"'))
print("  three.js vendor:", html.count("vendor/three.module.js"))
print("  cards:", html.count('class="card"'))
print("  unclosed divs:", html.count("<div") - html.count("</div>"))

# Verify artifact links exist
for f in ["una-manera-sencilla-de-orar.html", "catecismo-menor.html", "enchiridion.html"]:
    p = ROOT / f
    print(f"  {f}: exists={p.exists()} size={p.stat().st_size if p.exists() else 0}")

# Verify platform badge
print()
print("=== platform badge ===")
manifest = ROOT / "platform-manifest.json"
if manifest.exists():
    m = manifest.read_text(encoding="utf-8")
    print("  manifest bytes:", len(m))
    print("  manifest sha256:", hashlib.sha256(m.encode()).hexdigest()[:16])
receipt = ROOT / "platform.aqr.json"
if receipt.exists():
    r = receipt.read_text(encoding="utf-8")
    print("  receipt bytes:", len(r))
    print("  receipt sha256:", hashlib.sha256(r.encode()).hexdigest()[:16])
