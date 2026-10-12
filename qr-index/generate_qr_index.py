#!/usr/bin/env python3
"""
QR Index Generator — genera códigos QR para el índice de plugins de Hermes Desktop.

Cada QR contiene: nombre, descripción, path, y capabilities del plugin.
Un QR maestro indexa todos los plugins.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add vision-supervision to path
sys.path.insert(0, str(Path(r"C:\æ\vision-supervision")))

from vision_supervision.qr_coder import QRCoder, QRBatchCoder


def collect_plugins() -> list:
    """Collect all Hermes Desktop plugins."""
    plugins = []
    
    for base_dir in [
        r"C:\Users\yaelm\AppData\Local\hermes\desktop-plugins",
        r"C:\Users\yaelm\AppData\Local\hermes\plugins"
    ]:
        if not os.path.exists(base_dir):
            continue
        
        for name in sorted(os.listdir(base_dir)):
            plugin_dir = os.path.join(base_dir, name)
            if not os.path.isdir(plugin_dir):
                continue
            
            plugin = {
                "name": name,
                "path": plugin_dir,
                "registered_at": datetime.now(timezone.utc).isoformat(),
            }
            
            # Extract description from __init__.py
            init_path = os.path.join(plugin_dir, "__init__.py")
            if os.path.exists(init_path):
                with open(init_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if '"""' in content:
                        start = content.index('"""') + 3
                        end = content.index('"""', start)
                        plugin["description"] = content[start:end].strip().split('\n')[0]
            
            # Check for capabilities
            yaml_path = os.path.join(plugin_dir, "plugin.yaml")
            if os.path.exists(yaml_path):
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    yaml_content = f.read()
                    if 'provides_tools' in yaml_content:
                        plugin["has_tools"] = True
            
            # Check for API
            api_path = os.path.join(plugin_dir, "dashboard", "plugin_api.py")
            if os.path.exists(api_path):
                plugin["has_api"] = True
            
            # Check for desktop plugin.js
            js_path = os.path.join(plugin_dir, "plugin.js")
            if os.path.exists(js_path):
                plugin["has_desktop"] = True
            
            plugins.append(plugin)
    
    return plugins


def generate_plugin_qr(plugin: dict, coder: QRCoder, output_dir: str) -> dict:
    """Generate a QR code for a single plugin."""
    # Compact plugin data for QR
    qr_data = {
        "n": plugin["name"],
        "d": plugin.get("description", ""),
        "p": plugin["path"],
        "t": plugin.get("has_tools", False),
        "a": plugin.get("has_api", False),
        "x": plugin.get("has_desktop", False),
    }
    
    # Remove empty fields
    qr_data = {k: v for k, v in qr_data.items() if v}
    
    json_str = json.dumps(qr_data, ensure_ascii=False, separators=(',', ':'))
    
    filepath = str(Path(output_dir) / f"plugin_{plugin['name']}.png")
    
    try:
        qr = coder.codificar(json_str, filepath)
        return {
            "name": plugin["name"],
            "filepath": filepath,
            "version": qr.version,
            "size": qr.size,
            "hash": qr.hash,
        }
    except Exception as e:
        return {
            "name": plugin["name"],
            "error": str(e),
        }


def generate_master_index(plugins: list, coder: QRCoder, output_dir: str) -> dict:
    """Generate master index QR with all plugins."""
    # Compact index: just names and paths
    index_data = {
        "v": "1.0",
        "t": datetime.now(timezone.utc).isoformat(),
        "count": len(plugins),
        "plugins": [
            {
                "n": p["name"],
                "d": p.get("description", "")[:60],
            }
            for p in plugins
        ]
    }
    
    json_str = json.dumps(index_data, ensure_ascii=False, separators=(',', ':'))
    
    filepath = str(Path(output_dir) / "hermes_desktop_index.png")
    
    try:
        # Use chunked if too large
        if len(json_str) > 1000:
            lote = coder.codificar_chunked(json_str, output_dir)
            return {
                "filepath": filepath,
                "chunks": lote.total_chunks,
                "hash": lote.data_hash,
            }
        else:
            qr = coder.codificar(json_str, filepath)
            return {
                "filepath": filepath,
                "version": qr.version,
                "size": qr.size,
                "hash": qr.hash,
            }
    except Exception as e:
        return {
            "filepath": filepath,
            "error": str(e),
        }


def generate_html_index(plugins: list, qr_results: list, output_dir: str) -> str:
    """Generate HTML index page with all QR codes."""
    html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hermes Desktop — QR Plugin Index</title>
<style>
  :root { --void: #050505; --gold: #D4AF37; --ink: #f0ece4; --muted: rgba(240,236,228,.42); --border: rgba(212,175,55,.16); }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--void); color: var(--ink); font-family: 'JetBrains Mono', monospace; padding: 20px; }
  h1 { color: var(--gold); font-size: 18px; letter-spacing: 2px; margin-bottom: 8px; }
  .subtitle { color: var(--muted); font-size: 11px; margin-bottom: 24px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
  .card { border: 1px solid var(--border); border-radius: 6px; padding: 12px; background: rgba(5,5,5,.6); }
  .card h3 { color: var(--gold); font-size: 12px; margin-bottom: 6px; word-break: break-all; }
  .card .desc { color: var(--muted); font-size: 10px; margin-bottom: 8px; line-height: 1.4; }
  .card img { width: 100%; max-width: 200px; border-radius: 4px; display: block; margin: 0 auto; }
  .card .meta { color: var(--muted); font-size: 9px; margin-top: 8px; text-align: center; }
  .master { border: 2px solid var(--gold); margin-bottom: 24px; text-align: center; }
  .master img { max-width: 300px; }
  .scan { position: fixed; inset: 0; pointer-events: none; z-index: 5; background: repeating-linear-gradient(0deg, transparent 0px, transparent 2px, rgba(212,175,55,.015) 2px, rgba(212,175,55,.015) 4px); }
</style>
</head>
<body>
<div class="scan"></div>
<h1>Hermes Desktop — QR Plugin Index</h1>
<div class="subtitle">""" + f"{len(plugins)} plugins · generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}" + """</div>

<div class="grid">
"""
    
    for plugin, qr_result in zip(plugins, qr_results):
        if "error" in qr_result:
            continue
        
        desc = plugin.get("description", "")[:80]
        html += f"""  <div class="card">
    <h3>{plugin['name']}</h3>
    <div class="desc">{desc}</div>
    <img src="{Path(qr_result['filepath']).name}" alt="{plugin['name']}">
    <div class="meta">v{qr_result.get('version', '?')} · {qr_result.get('size', ('?','?'))[0]}×{qr_result.get('size', ('?','?'))[1]} · {qr_result.get('hash', '?')[:8]}</div>
  </div>
"""
    
    html += """</div>
</body>
</html>"""
    
    filepath = str(Path(output_dir) / "index.html")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return filepath


def main():
    output_dir = r"C:\æ\qr-index\hermes-desktop"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    print("Collecting plugins...")
    plugins = collect_plugins()
    print(f"Found {len(plugins)} plugins")
    
    coder = QRCoder(error_correction='M', box_size=8, border=3)
    
    print("\nGenerating plugin QRs...")
    qr_results = []
    for plugin in plugins:
        result = generate_plugin_qr(plugin, coder, output_dir)
        qr_results.append(result)
        if "error" in result:
            print(f"  ❌ {plugin['name']}: {result['error']}")
        else:
            print(f"  ✅ {plugin['name']}: v{result['version']} {result['size']}")
    
    print("\nGenerating master index...")
    master = generate_master_index(plugins, coder, output_dir)
    print(f"  Master: {master}")
    
    print("\nGenerating HTML index...")
    html_path = generate_html_index(plugins, qr_results, output_dir)
    print(f"  HTML: {html_path}")
    
    # Save JSON index
    json_path = str(Path(output_dir) / "index.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "plugin_count": len(plugins),
            "plugins": plugins,
            "qr_results": qr_results,
            "master_index": master,
        }, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {json_path}")
    
    print(f"\n✅ QR Index generated at {output_dir}")
    print(f"   {len(plugins)} plugins indexed")
    print(f"   {len([r for r in qr_results if 'error' not in r])} QRs generated")


if __name__ == "__main__":
    main()
