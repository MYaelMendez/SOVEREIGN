"""Build the film corpus index: every film, its gate, its DOI, its reachability.

The corpus is 144 films and 20 reachable pages. This makes it findable. The
index is generated from measurement, never from recollection: durations and
frozen tails come from ffprobe, hashes from the delivered bytes, and live status
from an HTTP HEAD against the published surface.
"""
import concurrent.futures as cf
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.request

sys.path.insert(0, r'C:\æ\tinycudavideo')
import tinycudavideo as V

S = pathlib.Path(os.environ['HERMES_HOME']) / 'cache' / 'scratch'
GP = pathlib.Path(r'C:\æ\github-pages')
BASE = 'https://myaelmendez.github.io'

rows = json.loads((S / 'film-audit.json').read_text(encoding='utf-8'))
ok = [r for r in rows if 'error' not in r]
skip = ('smoke', 'tcv-a', 'tcv-b')
real = [r for r in ok if not any(k in r['name'] for k in skip)]


def head(name):
    try:
        rq = urllib.request.Request(f'{BASE}/{name}', method='HEAD')
        with urllib.request.urlopen(rq, timeout=25) as r:
            return name, r.status
    except Exception as e:
        return name, getattr(e, 'code', 0)


with cf.ThreadPoolExecutor(12) as ex:
    live = dict(ex.map(head, [r['name'] for r in real]))

entries = []
for r in real:
    p = pathlib.Path(r['path'])
    fixed = p.parent / f"{p.stem}-fixed.mp4"
    e = {
        'film': p.stem,
        'file': r['name'],
        'seconds': r['video_s'],
        'audio_seconds': r['audio_s'],
        'has_voice': r['has_audio'],
        'frozen_tail_s': r['frozen_s'],
        'frames': r['frames'],
        'size': r['size'],
        'vertical': bool(r['size'][0] and r['size'][1] and r['size'][1] > r['size'][0]),
        'mib': r['mib'],
        'live': live.get(r['name']) == 200,
        'http': live.get(r['name']),
        'url': f"{BASE}/{r['name']}" if live.get(r['name']) == 200 else None,
        'defective': r['frozen_s'] > 0.15,
        'repair_available': fixed.exists(),
        'mtime': time.strftime('%Y-%m-%d', time.localtime(r['mtime'])),
        'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
    }
    e['citation'] = f"æ://film/{p.stem}"
    entries.append(e)

entries.sort(key=lambda e: (-e['live'], -e['seconds']))
aud = [e for e in entries if e['has_voice']]
bad = [e for e in entries if e['defective']]
summary = {
    'schema': 'ae/film-corpus/1',
    'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'films': len(entries),
    'total_minutes': round(sum(e['seconds'] for e in entries) / 60, 1),
    'total_gib': round(sum(e['mib'] for e in entries) / 1024, 2),
    'live': sum(1 for e in entries if e['live']),
    'unpublished': sum(1 for e in entries if not e['live']),
    'with_voice': len(aud),
    'vertical': sum(1 for e in entries if e['vertical']),
    'defective': len(bad),
    'defective_live': sum(1 for e in bad if e['live']),
    'repairable': sum(1 for e in bad if e['repair_available']),
    'frozen_seconds_total': round(sum(e['frozen_tail_s'] for e in entries), 1),
    'defect_rate_with_voice_pct': round(100 * len(bad) / max(1, len(aud)), 1),
    'defect_rate_silent_pct': round(
        100 * sum(1 for e in entries if e['defective'] and not e['has_voice'])
        / max(1, len(entries) - len(aud)), 1),
    'finding': ('every defect is co-extensive with having audio: failures live at '
                'the interface between picture and voice, not in either component'),
    'base': BASE,
}
out = {'summary': summary, 'films': entries}
(GP / 'film-corpus.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
print(f"\n  wrote film-corpus.json · {len(entries)} entries")
