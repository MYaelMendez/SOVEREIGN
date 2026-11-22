#!/usr/bin/env python3
"""mixture_composite — the performed cues become the 2x3 mixture canvas.

The mixture-of-robots family is five bodies plus ONE authority, in a 2x3 grid.
Each panel is a governed performance: the actor, its verb and its camera come
from the script; the composite adds the panel identity and the gate tile.

    python mixture_composite.py <script.json> --clips <dir> --out <film.mp4>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FFMPEG = os.environ.get('FFMPEG', 'C:/Users/yaelm/AppData/Local/hermes/tools/'
                                 'ffmpeg-7.1-nvenc/bin/ffmpeg.exe')
FONT = Path('C:/æ/github-pages/aipodcast_me/assets/fonts/JetBrainsMono-700.ttf')
COLS, ROWS = 2, 3
W, H = 720, 1280
TILE_W, TILE_H = W // COLS, H // ROWS


def gate_tile(out: Path) -> None:
    """The sixth panel: the authority. Not a body — the gate."""
    img = Image.new('RGB', (TILE_W, TILE_H), (22, 19, 13))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(str(FONT), 22)
    fs = ImageFont.truetype(str(FONT), 15)
    d.rectangle([10, 10, TILE_W - 10, TILE_H - 10], outline=(212, 175, 55), width=2)
    d.text((26, 60), 'AUTHORITY', font=f, fill=(212, 175, 55))
    for i, (k, v) in enumerate([('scheme', 'HUMAN://ROOT'),
                                ('motion', 'REFUSED'),
                                ('rules', 'ACT-001 · AUTH-002'),
                                ('grants', 'false')]):
        d.text((26, 130 + i * 46), k, font=fs, fill=(111, 106, 92))
        d.text((150, 130 + i * 46), v, font=fs, fill=(232, 230, 223))
    d.text((26, TILE_H - 60), 'one human · many robots', font=fs, fill=(212, 175, 55))
    img.save(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('script')
    ap.add_argument('--clips', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    spec = json.loads(Path(a.script).read_text(encoding='utf-8'))
    cues = sorted(spec['cues'], key=lambda c: float(c['t']))
    clips = sorted(Path(a.clips).glob('cue*.mp4'))
    if len(clips) < 5:
        print(json.dumps({'ok': False, 'reason': f'need 5 clips, found {len(clips)}'}))
        return 1

    work = Path(a.out).parent / (Path(a.out).stem + '-mix')
    work.mkdir(parents=True, exist_ok=True)
    gate_tile(work / 'gate.png')

    # drawtext cannot take a non-ASCII path, and the drive colon must be
    # escaped in a filter string — stage an ASCII copy of the font.
    import shutil
    import tempfile
    fdir = Path(tempfile.gettempdir()) / 'ae-font'
    fdir.mkdir(parents=True, exist_ok=True)
    fpath = fdir / FONT.name
    shutil.copy(FONT, fpath)
    ff_font = str(fpath).replace('\\', '/').replace(':', '\\:')

    # one tile per body, labelled with the actor and its verb
    tiles = []
    for i, (cue, clip) in enumerate(zip(cues[:5], clips[:5])):
        tile = work / f'tile{i}.mp4'
        vf = (f"scale={TILE_W}:{TILE_H},"
              f"drawtext=fontfile='{ff_font}':text='{cue['actor']} · {cue['verb']}':"
              f"x=12:y=12:fontsize=16:fontcolor=0xD4AF37:box=1:boxcolor=0x000000AA")
        r = subprocess.run([FFMPEG, '-y', '-i', str(clip), '-vf', vf,
                            '-r', '24', '-c:v', 'h264_nvenc', '-preset', 'p5',
                            '-b:v', '4M', str(tile)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(json.dumps({'ok': False, 'reason': (r.stderr or '')[-300:]}))
            return 1
        tiles.append(tile)
    gate_v = work / 'gate.mp4'
    subprocess.run([FFMPEG, '-y', '-loop', '1', '-i', str(work / 'gate.png'),
                    '-t', '15', '-r', '24', '-vf', f'scale={TILE_W}:{TILE_H}',
                    '-c:v', 'h264_nvenc', '-preset', 'p5', '-b:v', '1M',
                    str(gate_v)], capture_output=True, text=True)
    tiles.append(gate_v)

    # a gold grid over the six panels: structural, and it lifts the mean
    # luminance of a grid whose tiles are individually dark
    frame = work / 'frame.png'
    fi = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fi)
    for x in (0, TILE_W, W - 2):
        fd.rectangle([x, 0, x + 2, H], fill=(212, 175, 55, 255))
    for y in (0, TILE_H, H - 2):
        fd.rectangle([0, y, W, y + 2], fill=(212, 175, 55, 255))
    fi.save(frame)

    order = [tiles[0], tiles[1], tiles[2], tiles[3], tiles[4], tiles[5]]
    fc = (f"[0:v][1:v][2:v]hstack=inputs=3[top];"
          f"[3:v][4:v][5:v]hstack=inputs=3[bot];"
          f"[top][bot]vstack=inputs=2[mix]")
    r = subprocess.run([FFMPEG, '-y', *[x for t in order for x in ('-i', str(t))],
                        '-i', str(frame),
                        '-filter_complex', fc + f",[mix][6:v]overlay=0:0:format=auto[out]",
                        '-map', '[out]',
                        '-r', '24', '-c:v', 'h264_nvenc', '-preset', 'p5',
                        '-b:v', '6M', a.out], capture_output=True, text=True)
    b = Path(a.out).read_bytes() if Path(a.out).exists() else b''
    print(json.dumps({'ok': r.returncode == 0 and bool(b),
                      'film': a.out, 'bytes': len(b),
                      'sha256': hashlib.sha256(b).hexdigest() if b else None,
                      'tiles': [t.name for t in tiles],
                      'panels': len(order), 'size': [W, H],
                      'stderr': (r.stderr or '')[-200:]}, indent=2))
    return 0 if r.returncode == 0 and b else 1


if __name__ == '__main__':
    raise SystemExit(main())
