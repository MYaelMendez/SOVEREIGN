#!/usr/bin/env python3
"""Render the 9:16 poster — deterministic, local, gold on void.

The poster states the thesis and the one number that proves it: the camera fix
(21 px -> 589 px). No ML, no CDN, no network.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
VOID = (5, 5, 5)
GOLD = (212, 175, 55)
GOLD2 = (240, 212, 135)
INK = (232, 230, 223)
MUTED = (111, 106, 92)
LINE = (66, 58, 34)

FONTS = Path('C:/æ/github-pages/aipodcast_me/assets/fonts')
MONO = {400: FONTS / 'JetBrainsMono-400.ttf', 700: FONTS / 'JetBrainsMono-700.ttf'}
DISP = FONTS / 'Orbitron-700.ttf'


def f(path, size):
    return ImageFont.truetype(str(path), size)


def scanlines(img):
    px = img.load()
    for y in range(0, H, 4):
        for x in range(W):
            r, g, b = px[x, y][:3]
            px[x, y] = (int(r * .82), int(g * .82), int(b * .82))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='verbs/out/poster-916.png')
    a = ap.parse_args()

    img = Image.new('RGB', (W, H), VOID)
    d = ImageDraw.Draw(img)

    f_disp = f(DISP, 78)
    f_h1 = f(DISP, 54)
    f_mono = f(MONO[400], 25)
    f_mono_s = f(MONO[400], 21)
    f_mono_xs = f(MONO[400], 18)
    f_mono_b = f(MONO[700], 25)
    f_lbl = f(MONO[700], 20)

    y = 96
    d.text((70, y), 'æ://', font=f(DISP, 40), fill=GOLD)
    d.text((238, y + 12), 'GOVERNANCE AND PROVENANCE LABORATORY',
           font=f_mono_xs, fill=MUTED)
    y += 74
    d.line([(70, y), (W - 70, y)], fill=LINE, width=2)
    y += 56

    # headline
    d.text((70, y), 'THE FILM IS', font=f_h1, fill=GOLD)
    y += 72
    d.text((70, y), 'AN INSTRUMENT.', font=f_h1, fill=GOLD)
    y += 118

    for line in ['A policy trace becomes a film. The film is',
                 'graded by a second instrument. The verdict',
                 'becomes the input of the next run.']:
        d.text((70, y), line, font=f_mono, fill=INK)
        y += 34
    y += 34

    # the loop, vertical
    steps = ['policy trace', 'render · real CAD', 'supervise', 'track',
             'compare', 'receipt', 'next run']
    for i, s in enumerate(steps):
        d.rounded_rectangle([70, y, W - 70, y + 54], radius=6,
                            outline=LINE, fill=(14, 13, 9))
        d.text((94, y + 14), s, font=f_mono_b, fill=GOLD2)
        y += 54
        if i < len(steps) - 1:
            d.text((W // 2 - 8, y + 2), '▼', font=f_mono_s, fill=MUTED)
            y += 30
    y += 44

    # the number
    d.line([(70, y), (W - 70, y)], fill=LINE, width=2)
    y += 40
    d.text((70, y), 'THE CAMERA FIX', font=f_lbl, fill=GOLD)
    y += 42
    d.text((70, y), 'camera tracks the body', font=f_mono_s, fill=MUTED)
    d.text((W - 250, y), '21 px', font=f_mono_b, fill=MUTED)
    y += 40
    d.text((70, y), 'free root, camera held', font=f_mono_s, fill=INK)
    d.text((W - 290, y), '589 px', font=f(DISP, 34), fill=GOLD2)
    y += 52
    d.text((70, y), '3.118 m carried · 1 track · 216 frames · 189 px/m',
           font=f_mono_xs, fill=MUTED)
    y += 62

    # verbs
    d.line([(70, y), (W - 70, y)], fill=LINE, width=2)
    y += 40
    d.text((70, y), 'NINE VERBS', font=f_lbl, fill=GOLD)
    y += 44
    d.text((70, y), 'PROVEN', font=f_mono_b, fill=(0, 255, 157))
    d.text((250, y), 'stand · walk · turn · strafe · set_velocity',
           font=f_mono_s, fill=INK)
    y += 44
    d.text((70, y), 'REFUSED', font=f_mono_b, fill=(255, 107, 125))
    d.text((250, y), 'damp · balance · trajectory · set_joints',
           font=f_mono_s, fill=MUTED)
    y += 70

    # receipts
    d.text((70, y), 'loop-09', font=f_mono_xs, fill=GOLD)
    d.text((70, y + 26), '2c3edd20eb4a509f', font=f_mono_xs, fill=MUTED)
    d.text((70, y + 58), 'verbs-09', font=f_mono_xs, fill=GOLD)
    d.text((70, y + 84), '67b61520f5604cd5', font=f_mono_xs, fill=MUTED)
    y += 140

    d.line([(70, y), (W - 70, y)], fill=LINE, width=2)
    y += 34
    d.text((70, y), '#opensourceware', font=f_mono_s, fill=GOLD)
    d.text((70, y + 34), '#hermiphicationisinevitable', font=f_mono_xs, fill=MUTED)

    scanlines(img)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    b = out.read_bytes()
    print(json.dumps({'file': str(out), 'bytes': len(b), 'size': [W, H],
                      'ratio': '9:16', 'sha256': hashlib.sha256(b).hexdigest()},
                     indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
