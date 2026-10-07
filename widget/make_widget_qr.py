#!/usr/bin/env python3
"""make_widget_qr.py — render the widget's manifest envelope as a QR (SVG, no PIL).

The QR is only the ADDRESS. It carries the æ:// manifest envelope; trust is
re-established by re-hashing the WASM module against the manifest, never by
trusting the QR bytes.
"""
import sys
sys.path.insert(0, "C:/æ/agents")
import qrcode
from qrcode.image.svg import SvgPathImage
from qrcode.constants import ERROR_CORRECT_M

env_path = "C:/æ/widget/widget.envelope.txt"
envelope = open(env_path, encoding="utf-8").read().strip()

qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M, box_size=10, border=2)
qr.add_data(envelope)
qr.make(fit=True)
img = qr.make_image(image_factory=SvgPathImage)

out = "C:/æ/widget/widget-qr.svg"
img.save(out)
print("QR saved:", out)
print("envelope bytes:", len(envelope))
print("qr version:", qr.version, "modules:", qr.modules_count)
