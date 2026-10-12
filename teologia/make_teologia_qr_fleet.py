#!/usr/bin/env python3
"""make_teologia_qr_fleet.py — generate QR fleet for teologia.ai.

Each QR is only an ADDRESS. Trust is re-established by re-hashing the
WASM module against the manifest, never by trusting the QR bytes.

Fleet:
  1. biblia-del-oso.html  — Salmo 23 (Biblia del Oso, 1569)
  2. biblia-del-oso.mp4   — video render (NVENC, 450 frames)
  3. hauge-teologia.html  — Haugean Legacy · LALI
  4. teologia-index.html  — hub central (æ://teologia)
"""
import sys, os, json, hashlib
sys.path.insert(0, "C:/æ/agents")
import qrcode
from qrcode.image.svg import SvgPathImage
from qrcode.constants import ERROR_CORRECT_M

OUT_DIR = "C:/æ/teologia/qr"
os.makedirs(OUT_DIR, exist_ok=True)

# ── Fleet definition ──
FLEET = [
    {
        "id": "biblia-del-oso-html",
        "label": "Biblia del Oso — Salmo 23 (HTML)",
        "url": "https://myaelmendez.github.io/biblia-del-oso.html",
        "type": "page",
    },
    {
        "id": "biblia-del-oso-mp4",
        "label": "Biblia del Oso — Salmo 23 (MP4)",
        "url": "https://myaelmendez.github.io/biblia-del-oso.mp4",
        "type": "video",
    },
    {
        "id": "hauge-teologia",
        "label": "Haugean Legacy · teologia.ai",
        "url": "https://myaelmendez.github.io/hauge-teologia.html",
        "type": "page",
    },
    {
        "id": "teologia-index",
        "label": "æ://teologia — Hub Central",
        "url": "https://myaelmendez.github.io/teologia/",
        "type": "hub",
    },
]

# ── Generate QRs ──
manifest = {"fleet": "teologia.ai", "generated": "2026-10-08", "qrs": []}

for item in FLEET:
    url = item["url"]
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(image_factory=SvgPathImage)

    out_path = os.path.join(OUT_DIR, f"{item['id']}.svg")
    img.save(out_path)

    size = os.path.getsize(out_path)
    print(f"  ✅ {item['id']}: v{qr.version}, {qr.modules_count} modules, {size} bytes")

    manifest["qrs"].append({
        "id": item["id"],
        "label": item["label"],
        "url": url,
        "type": item["type"],
        "qr_version": qr.version,
        "modules": qr.modules_count,
        "svg": f"qr/{item['id']}.svg",
    })

# ── Write manifest ──
manifest_path = os.path.join(OUT_DIR, "manifest.json")
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
print(f"\n📋 Manifest: {manifest_path}")

# ── Generate index HTML ──
index_html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>æ://teologia — QR Fleet</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&display=swap');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #0a0a0a;
    color: #d4af37;
    font-family: 'Cormorant Garamond', serif;
    min-height: 100vh;
    padding: 40px 20px;
  }
  .container { max-width: 800px; margin: 0 auto; }
  h1 {
    font-family: 'Cinzel', serif;
    font-size: 32px;
    letter-spacing: 4px;
    text-align: center;
    margin-bottom: 8px;
    color: #d4af37;
  }
  .subtitle {
    text-align: center;
    color: rgba(212,175,55,0.5);
    font-size: 14px;
    letter-spacing: 2px;
    margin-bottom: 40px;
  }
  .qr-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 24px;
  }
  .qr-card {
    background: rgba(212,175,55,0.03);
    border: 1px solid rgba(212,175,55,0.15);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    transition: border-color 0.2s;
  }
  .qr-card:hover { border-color: rgba(212,175,55,0.4); }
  .qr-card img {
    width: 180px;
    height: 180px;
    margin-bottom: 16px;
    filter: invert(78%) sepia(55%) saturate(500%) hue-rotate(3deg) brightness(1.05);
  }
  .qr-card h3 {
    font-family: 'Cinzel', serif;
    font-size: 14px;
    letter-spacing: 1px;
    margin-bottom: 8px;
    color: #d4af37;
  }
  .qr-card .url {
    font-size: 11px;
    color: rgba(212,175,55,0.4);
    word-break: break-all;
    font-family: 'JetBrains Mono', monospace;
  }
  .qr-card .type {
    display: inline-block;
    margin-top: 8px;
    padding: 2px 8px;
    border: 1px solid rgba(212,175,55,0.2);
    border-radius: 3px;
    font-size: 9px;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: rgba(212,175,55,0.6);
  }
  .footer {
    text-align: center;
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid rgba(212,175,55,0.1);
    color: rgba(212,175,55,0.3);
    font-size: 11px;
    letter-spacing: 2px;
  }
</style>
</head>
<body>
  <div class="container">
    <h1>æ://TEOLOGIA</h1>
    <p class="subtitle">QR FLEET · OPEN SOURCE SINCE 1517</p>
    <div class="qr-grid">
"""

for item in manifest["qrs"]:
    index_html += f"""      <div class="qr-card">
        <img src="{item['svg']}" alt="{item['label']}">
        <h3>{item['label']}</h3>
        <p class="url">{item['url']}</p>
        <span class="type">{item['type']}</span>
      </div>
"""

index_html += """    </div>
    <div class="footer">
      TEOLOGIA.AI · BIBLIA DEL OSO · CASIODORO DE REINA 1569
    </div>
  </div>
</body>
</html>
"""

index_path = os.path.join(OUT_DIR, "index.html")
with open(index_path, "w", encoding="utf-8") as f:
    f.write(index_html)
print(f"🌐 Index: {index_path}")

print(f"\n✅ Fleet complete: {len(manifest['qrs'])} QRs generated")
