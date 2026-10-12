#!/usr/bin/env python3
"""Update index.html: insert the Catecismo Mayor card (04) and update badge count."""
from pathlib import Path

INDEX = Path(r"C:\æ\site\teologia\index.html")
html = INDEX.read_text(encoding="utf-8")

# Compute real hashes for the card meta
import hashlib
hash_mayor = hashlib.sha256((Path(r"C:\æ\site\teologia") / "catecismo-mayor.html").read_bytes()).hexdigest()

# The 4th card HTML
CARD_04 = f'''  <!-- Artifact 4: Catecismo Mayor -->
  <a class="card" href="catecismo-mayor.html">
    <div class="num">04</div>
    <div class="label">Catecismo Mayor</div>
    <div class="desc">Lutero, 1529. Expansión del Menor para la escuela y el púlpito: explicaciones extensas de los Diez Mandamientos, Credo, Padre Nuestro, Bautismo y Sacramento del Altar.</div>
    <div class="meta">
      <span class="hash">sha256 · {hash_mayor[:16]}…</span>
      <span>· 86 KB HTML</span>
      <span>· 306 KB PDF</span>
    </div>
    <div class="links">
      <a href="catecismo-mayor.html">LEER</a>
      <a class="ghost" href="catecismo-mayor.pdf" download="catecismo-mayor.pdf">⤓ PDF</a>
    </div>
  </a>

  <!-- Badge row -->'''

# Replace the badge row opening comment with card 04 + badge row
html = html.replace("  <!-- Badge row -->", CARD_04)

# Update badge count text
html = html.replace("3 artefactos · 3 chips verificados", "4 artefactos · 4 chips verificados")

# Update node positions: add a 4th node
old_nodes = """  const nodePositions = [
    new THREE.Vector3(-2.5, 1.5, -2),
    new THREE.Vector3(2.5, 1.5, -2),
    new THREE.Vector3(0, -2, -3),
  ];"""
new_nodes = """  const nodePositions = [
    new THREE.Vector3(-3, 1.5, -2),
    new THREE.Vector3(-1, 2.5, -3),
    new THREE.Vector3(1, 2.5, -3),
    new THREE.Vector3(3, 1.5, -2),
  ];"""
html = html.replace(old_nodes, new_nodes)

INDEX.write_text(html, encoding="utf-8")
cards = 'class="card"'
print(f"index.html updated: {len(html)} bytes")
print(f"  cards: {html.count(cards)}")
print(f"  4th node: {html.count('nodePositions')}")
print(f"  mayor card: {'catecismo-mayor.html' in html}")
