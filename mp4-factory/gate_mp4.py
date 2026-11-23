#!/usr/bin/env python3
"""Gate an encoded 9:16 MP4 by decoding its bytes back. Usage: gate_mp4.py <mp4>."""
from __future__ import annotations

import hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image

FFMPEG = Path('C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-7.1-nvenc/bin/ffmpeg.exe')


def gate(path: Path) -> dict:
    out = Path(str(path) + '.frames')
    out.mkdir(exist_ok=True)
    for p in out.glob('d*.png'): p.unlink()
    r = subprocess.run([str(FFMPEG), '-v', 'error', '-i', str(path), str(out / 'd%05d.png')],
                       capture_output=True, text=True, timeout=300)
    if r.returncode:
        return {'ok': False, 'refused': True, 'reason': 'decode failed: ' + r.stderr[-160:]}
    files = sorted(out.glob('d*.png'))
    ims = [np.asarray(Image.open(p).convert('L'), dtype=np.float32) for p in files[::4]]
    lum = min(float(x.mean()) for x in ims)
    con = min(float(x.std()) for x in ims)
    mot = max(float(np.abs(ims[i].astype(int) - ims[i-1].astype(int)).mean())
              for i in range(1, len(ims)))
    unique = len({hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    checks = {'frames': len(files) > 0, 'luminance': lum > 20,
              'contrast': con > 10, 'motion': mot > 0.3, 'unique': unique > 1}
    return {'ok': all(checks.values()), 'checks': checks, 'decoded_frames': len(files),
            'unique_frames': unique, 'luminance_min': round(lum, 2),
            'contrast_min': round(con, 2), 'motion_max': round(mot, 3)}


if __name__ == '__main__':
    p = Path(sys.argv[1]);
    print(json.dumps(gate(p), indent=2))
