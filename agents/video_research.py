#!/usr/bin/env python3
"""video_research — the film is the paper. The receipt is the DOI.

We have been doing science with video and not keeping a lab notebook. 65 films
published, 2 receipts persisted, ZERO gate records saved to disk. The metrics
were printed to a terminal and lost. That is not research; that is demonstration.

This fixes it. Every film gets a permanent record with the parts a paper has:

    abstract     what the film claims
    methods      the spec, the harness, the device, the model hash
    results      measured luminance, contrast, motion, black frames, audio
    data         the trace, if the motion came from a policy
    limitations  what this film does NOT establish
    citation     a stable handle: the SHA-256 of the delivered bytes

    vr record <film>     measure and write the record
    vr index             the corpus, as a research index
    vr cite <film>       the citation line

THE RULE
    A measurement is taken NOW and dated. If a metric was not persisted at
    render time, the record says `re_measured` — it does not pretend the number
    was captured then. A film with no surviving spec is marked
    `methods: unavailable`, not reconstructed from memory.

    Lost data is a finding. Inventing it would be the exact failure the whole
    chain exists to prevent.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SITE = Path(os.environ.get('AE_SITE', 'C:/æ/github-pages'))
RECORDS = Path(os.environ.get('AE_RESEARCH_OUT', SITE / 'research'))


def ffmpeg() -> Path:
    h = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
    p = h / 'tools' / 'ffmpeg-7.1-nvenc' / 'bin'
    if p.exists():
        return p
    import shutil
    w = shutil.which('ffmpeg')
    if not w:
        raise SystemExit('ffmpeg not found')
    return Path(w).parent


def measure(film: Path) -> dict:
    """Re-measure the delivered artifact. Not the render log — the file itself."""
    ff = ffmpeg()
    probe = subprocess.run([str(ff / 'ffprobe'), '-v', 'error', '-show_entries',
                            'stream=codec_type,nb_frames,duration,width,height,r_frame_rate',
                            '-show_entries', 'format=duration', '-of', 'json', str(film)],
                           capture_output=True, text=True, timeout=180)
    st = {s['codec_type']: s for s in json.loads(probe.stdout or '{}').get('streams', [])}
    v = st.get('video', {})
    a = st.get('audio', {})
    out = {'width': v.get('width'), 'height': v.get('height'),
           'frames': int(v.get('nb_frames') or 0),
           'video_s': float(v.get('duration') or 0),
           'audio_s': float(a.get('duration') or 0)}
    out['av_delta_s'] = round(abs(out['video_s'] - out['audio_s']), 3)
    out['av_matched'] = out['av_delta_s'] < 0.15

    # picture metrics at a fixed analysis scale, so films are comparable
    r = subprocess.run([str(ff / 'ffmpeg'), '-v', 'error', '-i', str(film),
                        '-vf', 'scale=180:320', '-pix_fmt', 'gray',
                        '-f', 'rawvideo', '-'], capture_output=True, timeout=1800)
    if r.stdout:
        n = len(r.stdout) // (180 * 320)
        x = np.frombuffer(r.stdout[:n * 180 * 320], np.uint8).reshape(n, 320, 180).astype(np.float32)
        out['luminance'] = round(float(x.mean()), 2)
        out['contrast'] = round(float(x.std(axis=(1, 2)).mean()), 2)
        out['motion'] = round(float(np.abs(np.diff(x, axis=0)).mean()), 3) if n > 1 else 0.0
        out['black_frames'] = int((x.mean(axis=(1, 2)) < 3).sum())
        out['analysis_scale'] = [180, 320]
    # audio
    r2 = subprocess.run([str(ff / 'ffmpeg'), '-v', 'error', '-i', str(film),
                         '-map', '0:a', '-ac', '1', '-ar', '24000',
                         '-f', 's16le', '-'], capture_output=True, timeout=900)
    if r2.stdout:
        y = np.frombuffer(r2.stdout, np.int16).astype(np.float32) / 32768
        w = 2400; m = len(y) // w
        if m:
            rms = np.sqrt((y[:m * w].reshape(m, w) ** 2).mean(axis=1))
            out['audio_rms'] = round(float(np.sqrt((y ** 2).mean())), 4)
            out['audio_peak'] = round(float(np.abs(y).max()), 3)
            out['near_silent_pct'] = round(float(100 * (rms < 0.005).sum() / m), 1)
    else:
        out['audio'] = 'none'
    return out


def find_artifacts(film: Path) -> dict:
    """Locate the surviving methods and data. Never reconstruct from memory."""
    stem = film.stem.replace('-916', '')
    arts = {'spec': None, 'trace': None, 'receipt': None, 'render_meta': None}
    for p in SITE.glob(f'spec-*{stem}*.json'):
        arts['spec'] = str(p); break
    if arts['spec'] is None:
        for p in SITE.glob(f'spec-{stem}*.json'):
            arts['spec'] = str(p); break
    for p in SITE.glob(f'*{stem}*receipt*.json'):
        arts['receipt'] = str(p); break
    for p in SITE.glob(f'*{stem}*trace*.json'):
        arts['trace'] = str(p); break
    return arts


def record(film: Path, abstract: str = '', limitations: list[str] | None = None) -> dict:
    if not film.exists():
        return {'ok': False, 'reason': f'no such film: {film}'}
    sha = hashlib.sha256(film.read_bytes()).hexdigest()
    m = measure(film)
    arts = find_artifacts(film)
    methods = {'available': arts['spec'] is not None}
    if arts['spec']:
        try:
            s = json.loads(Path(arts['spec']).read_text(encoding='utf-8'))
            methods.update({'spec': arts['spec'],
                            'scenes': len(s.get('scenes', [])),
                            'texture': s.get('texture'),
                            'cast': s.get('cast')})
        except Exception:
            methods['available'] = False
    lim = limitations or [
        'Simulation only. No physical robot was involved.',
        'One machine. No second-box reproduction of this film.',
        'Gate metrics were not persisted at render time; re-measured from the delivered bytes.',
    ]
    if not m.get('av_matched'):
        lim.append(f"Audio/video duration mismatch of {m['av_delta_s']}s.")
    if m.get('near_silent_pct', 0) > 5:
        lim.append(f"{m['near_silent_pct']}% of audio windows are near-silent.")
    rec = {
        'schema': 'ae/video-research/1',
        'title': film.stem,
        'citation': f'æ://film/{film.stem} · sha256:{sha[:16]}',
        'doi_equivalent': sha,
        'file': film.name, 'bytes': film.stat().st_size,
        'url': f'https://myaelmendez.github.io/{film.name}',
        'abstract': abstract or f'A 9:16 robot film, {m["frames"]} frames, {m["video_s"]:.2f}s.',
        'methods': methods,
        'results': m,
        'data': {'trace': arts['trace'], 'available': arts['trace'] is not None},
        'artifacts': arts,
        'limitations': lim,
        'measured_at': datetime.now(timezone.utc).isoformat(),
        'measurement_kind': 're_measured',
        'authority': 'HUMAN://ROOT', 'grants': False,
        'note': 'metrics taken from the delivered artifact on the date above, '
                'not recovered from a render log',
    }
    RECORDS.mkdir(parents=True, exist_ok=True)
    out = RECORDS / f'{film.stem}.json'
    out.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding='utf-8')
    rec['record'] = str(out)
    return {'ok': True, **rec}


def index() -> dict:
    RECORDS.mkdir(parents=True, exist_ok=True)
    recs = []
    for p in sorted(RECORDS.glob('*.json')):
        if p.name == 'index.json':
            continue
        try:
            recs.append(json.loads(p.read_text(encoding='utf-8')))
        except Exception:
            pass
    films = sorted(SITE.glob('*-916.mp4'))
    recorded = {r['file'] for r in recs}
    unrecorded = [f.name for f in films if f.name not in recorded]
    idx = {'schema': 'ae/video-research-index/1',
           'corpus': len(films), 'recorded': len(recs),
           'unrecorded': len(unrecorded), 'unrecorded_files': unrecorded[:20],
           'papers': [{'title': r['title'], 'citation': r['citation'],
                       'frames': r['results'].get('frames'),
                       'seconds': r['results'].get('video_s'),
                       'luminance': r['results'].get('luminance'),
                       'motion': r['results'].get('motion'),
                       'av_matched': r['results'].get('av_matched'),
                       'methods_available': r['methods'].get('available'),
                       'url': r['url']} for r in recs],
           'finding': f'{len(recs)} of {len(films)} films have a research record. '
                      f'{len(unrecorded)} were published without one.',
           'authority': 'HUMAN://ROOT', 'grants': False}
    (RECORDS / 'index.json').write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding='utf-8')
    return {'ok': True, **idx}


def main():
    ap = argparse.ArgumentParser(prog='vr')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('record'); r.add_argument('film'); r.add_argument('--abstract', default='')
    sub.add_parser('index')
    c = sub.add_parser('cite'); c.add_argument('film')
    b = sub.add_parser('batch'); b.add_argument('--limit', type=int, default=8)
    a = ap.parse_args()
    if a.cmd == 'record':
        res = record(Path(a.film), a.abstract)
    elif a.cmd == 'index':
        res = index()
    elif a.cmd == 'cite':
        p = RECORDS / f'{Path(a.film).stem}.json'
        if p.exists():
            d = json.loads(p.read_text(encoding='utf-8'))
            res = {'ok': True, 'citation': d['citation'], 'doi_equivalent': d['doi_equivalent'],
                   'url': d['url'], 'measured_at': d['measured_at']}
        else:
            res = {'ok': False, 'reason': 'no record; run vr record first'}
    else:
        films = sorted(SITE.glob('*-916.mp4'), key=lambda x: -x.stat().st_mtime)[:a.limit]
        done = []
        for f in films:
            r = record(f)
            done.append({'film': f.name, 'ok': r.get('ok'),
                         'frames': r.get('results', {}).get('frames'),
                         'av_matched': r.get('results', {}).get('av_matched')})
        res = {'ok': True, 'recorded': len(done), 'rows': done}
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
