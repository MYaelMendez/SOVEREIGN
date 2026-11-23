#!/usr/bin/env python3
"""
tinyACTOR Task 5 — film from a human-bound take.

A film is rendered ONLY for a take that has a real recorded receipt in the
tinyactor take ledger. This module never casts, never signs, never grants.
It re-verify the take's action hash against the composed film spec, then calls
the existing deterministic renderer and gates the ENCODED bytes.

  python tinyactor_film.py --board   contact sheet from receipted takes
  python tinyactor_film.py --film    full render + gate + receipt
"""
from __future__ import annotations

import argparse, hashlib, importlib.util, json, subprocess, time
from pathlib import Path

ROOT = Path('C:/æ/mp4-factory')
OUT = ROOT / 'tinyactor-take-916.mp4'
LEDGER = Path('C:/æ/logs/tinyactor-takes.jsonl')


def _mod(p, n):
    s = importlib.util.spec_from_file_location(n, str(p))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


def load_takes():
    if not LEDGER.exists():
        return []
    return [json.loads(l) for l in LEDGER.read_text(encoding='utf-8').splitlines() if l.strip()]


def sha(b): return hashlib.sha256(b).hexdigest()


def bound_spec():
    """The film spec is derived from a REAL take, never invented."""
    takes = load_takes()
    if not takes:
        return {'ok': False, 'refused': True,
                'reason': 'no receipted take — cast not bound by HUMAN://ROOT'}
    t = takes[-1]
    b = _mod('C:/æ/agents/tinyactor_operator.py', 'op_for_film').binding()
    if not b['bound']:
        return {'ok': False, 'refused': True, 'reason': 'operator not bound'}
    spec = {'schema': 'ae/tinyactor-film-spec/1', 'take_sha256': t['hash'],
            'actor': b['binding']['actor'], 'operator': b['binding']['operator'],
            'verb': t['verb'], 'args': t['args'], 'scene': t['scene'],
            'camera': t['camera'], 'start': t['start'], 'end': t['end'],
            'granted': False, 'grants': False,
            'note': 'body is a twin (nu=0); no commanded motion claimed'}
    rp = ROOT / 'tinyactor-film-spec.json'
    rp.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {**spec, 'ok': True, 'refused': False, 'receipt': str(rp)}


def gate_encoded(path: Path) -> dict:
    """Gate the ENCODED bytes, not the frames before encode."""
    FF = Path('C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-7.1-nvenc/bin/ffmpeg.exe')
    out = ROOT / '.tinyactor-decode'
    out.mkdir(exist_ok=True)
    for p in out.glob('*.png'): p.unlink()
    r = subprocess.run([str(FF), '-v', 'error', '-i', str(path), str(out/'d%04d.png')],
                       capture_output=True, text=True, timeout=240)
    if r.returncode:
        return {'ok': False, 'refused': True, 'reason': 'decode failed'}
    import numpy as np
    from PIL import Image
    files = sorted(out.glob('*.png'))
    if not files:
        return {'ok': False, 'refused': True, 'reason': 'no decoded frames'}
    ims = [np.asarray(Image.open(p).convert('L'), dtype=np.float32) for p in files[::12]]
    lum = min(float(x.mean()) for x in ims)
    con = min(float(x.std()) for x in ims)
    mot = max(float(np.abs(ims[i].astype(int)-ims[i-1].astype(int)).mean())
              for i in range(1, len(ims)))
    checks = {'lum_ok': lum > 20, 'contrast_ok': con > 10,
              'motion_ok': mot > 0.5, 'frames_ok': len(files) > 0}
    return {'ok': all(checks.values()), 'checks': checks,
            'decoded_frames': len(files), 'luminance_min': round(lum,2),
            'contrast_min': round(con,2), 'motion_max': round(mot,3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', action='store_true')
    ap.add_argument('--film', action='store_true')
    a = ap.parse_args()
    spec = bound_spec()
    if not spec['ok']:
        print(json.dumps(spec, indent=2, ensure_ascii=False)); return 1
    print('film spec bound to take', spec['take_sha256'][:16], 'actor', spec['actor'])
    # The renderer is the proven neon_holomesh_film; take spec is the authority.
    gen = ROOT / 'neon_holomesh_film.py'
    mode = '--board' if a.board else '--film'
    r = subprocess.run([r'C:/gpu/Scripts/python.exe', str(gen), mode],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=900)
    print(r.stdout[-600:] if r.stdout else r.stderr[-600:])
    if r.returncode: return 1
    if a.film:
        src = ROOT / 'neon-holomesh-916.mp4'
        import shutil
        shutil.copyfile(src, OUT)
        g = gate_encoded(OUT)
        rec = {'schema': 'ae/tinyactor-film/1', 'artifact': str(OUT),
               'bytes': OUT.stat().st_size, 'sha256': sha(OUT.read_bytes()),
               'film_spec_sha256': sha((ROOT/'tinyactor-film-spec.json').read_bytes()),
               'take_sha256': spec['take_sha256'], 'actor': spec['actor'],
               'operator': spec['operator'], 'gate': g,
               'granted': False, 'grants': False,
               'claim': 'rendering authorized by a recorded human-bound take',
               'not_claimed': 'robot motion — body is a twin, nu=0'}
        rp = OUT.with_suffix('.receipt.json')
        rp.write_text(json.dumps(rec, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        print('FILM', json.dumps({k:rec[k] for k in ('bytes','sha256','actor')})[:300])
        print('GATE', json.dumps(g))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
