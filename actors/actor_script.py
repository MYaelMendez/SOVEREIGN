#!/usr/bin/env python3
"""actor_script — a screenplay that drives robot actors.

The robots are ACTORS. A script says who is on stage, what each one DOES (a
policy verb, from its own trace), what it SAYS (a line), and where the camera
sits. The compiler renders each cue from the actor's OWN policy trace at the
scripted camera, then cuts the cues into a PROOF/1 film whose beats carry the
actor, the verb and the line.

    actor/script/1
      cast[]    {id, model, traces{verb: path}, name, head}
      cues[]    {t, actor, verb, line, camera{az, el, dist}}
      voice     {voice, seed}
      gates     {luminance, contrast, motion, black_pct}
      output    {name, receipt}

    python actor_script.py script.json [--dry] [--no-render]

Every cue is rendered, never keyed: the motion is the policy's, the camera is
the script's, the line is burned into the beat and spoken in the narration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RTX = ROOT / 'agents' / 'rtx_asimov.py'
PROOF = ROOT / 'proof' / 'proof1.py'
PY = os.environ.get('ACTOR_PYTHON', 'C:/gpu/Scripts/python.exe')


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _render_clip(cue: dict, cast: dict, out: Path, seconds: float) -> dict:
    """One cue = one clip, from the actor's own policy trace at the scripted camera."""
    tr = Path(cast['traces'][cue['verb']])
    cmd = [PY, str(RTX), '--trace', str(tr), '--out', str(out),
           '--seconds', str(seconds), '--fps', '24', '--silent',
           '--free-root', '--model-dir', cast['model']]
    cam = cue.get('camera') or {}
    if cam.get('az') is not None:
        cmd += ['--az', str(cam['az'])]
    if cam.get('el') is not None:
        cmd += ['--el', str(cam['el'])]
    if cam.get('dist') is not None:
        cmd += ['--dist', str(cam['dist'])]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and out.exists()
    return {'ok': ok, 'clip': str(out), 'verb': cue['verb'],
            'actor': cue['actor'], 'line': cue.get('line', ''),
            'camera': cam, 'stderr': (r.stderr or '')[-300:],
            'sha256': _sha(out) if ok else None}


def compile_script(spec_path: Path, dry: bool = False, render: bool = True) -> dict:
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    if spec.get('schema') != 'actor/script/1':
        return {'ok': False, 'refused': True,
                'reason': f"schema must be actor/script/1, got {spec.get('schema')}"}
    cast = {c['id']: c for c in spec['cast']}
    cues = sorted(spec['cues'], key=lambda c: float(c['t']))
    outdir = Path(spec.get('output', {}).get('workdir', HERE / 'out')) / spec['output']['name']
    clips = outdir / 'clips'
    clips.mkdir(parents=True, exist_ok=True)

    # the whole film is the cue sequence; each cue owns [t, next t)
    total = float(spec.get('seconds') or (cues[-1]['t'] + 3.0))
    per = [round(float(cues[i + 1]['t']) - float(cues[i]['t']), 3) if i + 1 < len(cues)
           else round(total - float(cues[i]['t']), 3) for i in range(len(cues))]

    rendered = []
    for i, (cue, secs) in enumerate(zip(cues, per)):
        if cue['actor'] not in cast:
            return {'ok': False, 'refused': True,
                    'reason': f"cue {i}: unknown actor {cue['actor']}"}
        if cue['verb'] not in cast[cue['actor']].get('traces', {}):
            return {'ok': False, 'refused': True,
                    'reason': f"cue {i}: actor {cue['actor']} has no trace for verb {cue['verb']}"}
        clip = clips / f"cue{i:02d}-{cue['actor']}-{cue['verb']}.mp4"
        if render and not dry:
            r = _render_clip(cue, cast[cue['actor']], clip, secs)
            if not r['ok']:
                return {'ok': False, 'refused': True,
                        'reason': f"cue {i} render failed: {r['stderr']}"}
        elif not dry and not clip.exists():
            return {'ok': False, 'refused': True,
                    'reason': f"cue {i}: clip missing ({clip}) and --no-render set"}
        rendered.append({'clip': str(clip), 'sha256': _sha(clip) if clip.exists() else None,
                         'actor': cue['actor'], 'verb': cue['verb'],
                         'line': cue.get('line', ''), 'seconds': secs,
                         'camera': cue.get('camera') or {}})

    # cut the cues into a PROOF/1 film: one beat per cue, the line in the label
    labels = [f"{r['actor']} · {r['verb']}" + (f" · “{r['line']}”" if r['line'] else '')
              for r in rendered]
    lines = [r['line'] for r in rendered if r['line']]
    proof = {
        'schema': 'proof/film/1',
        'title': spec.get('title', 'UNTITLED'),
        'tagline': spec.get('tagline', ''),
        'seconds': total, 'fps': 24, 'size': [720, 1280],
        'emoji': spec.get('emoji', {'symbol': '🎬', 'seed': 9}),
        'voice': {'text': ' '.join(lines) if lines else spec.get('voice', {}).get('text', ''),
                  'voice': spec.get('voice', {}).get('voice', 'hermes'),
                  'seed': spec.get('voice', {}).get('seed', 9),
                  'max_seconds': max(1.0, total - 0.4)},
        'beats': {'count': len(rendered),
                  'per_beat_seconds': round(total / max(1, len(rendered)), 3),
                  'sources_dir': str(clips),
                  'sources': [str(Path(r['clip']).name) for r in rendered],
                  'labels': labels},
        'overlay': {'beat_numeral': True,
                    'source_block': {'sha256_chars': 32, 'rect': [0, 540, 620, 720]},
                    'progress_cells': 'per_frame',
                    'footer': spec.get('footer', 'ACTOR/SCRIPT/1 · EVERY MOVE IS A POLICY'),
                    'lower_third': {'height': 250, 'fill': [22, 19, 13]}},
        'gates': spec.get('gates', {'luminance': 20, 'contrast': 10, 'motion': 0.5,
                                    'black_pct': 5, 'mux_delta_s': 0.15}),
        'output': {'name': spec['output']['name'], 'receipt': True, 'meta': True},
    }
    proof_path = outdir / f"{spec['output']['name']}.proof.json"
    proof_path.write_text(json.dumps(proof, indent=2, ensure_ascii=False), encoding='utf-8')

    result = {'ok': True, 'spec': str(spec_path), 'proof_spec': str(proof_path),
              'cues': len(rendered), 'seconds': total, 'clips': rendered,
              'voice_text': proof['voice']['text']}
    if render and not dry:
        r = subprocess.run([PY, str(PROOF), str(proof_path)], capture_output=True, text=True)
        tail = [l for l in (r.stdout or '').splitlines() if l.strip()][-3:]
        result['render'] = {'ok': r.returncode == 0, 'tail': tail}
        result['ok'] = r.returncode == 0
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description='actor_script — a screenplay for robot actors')
    ap.add_argument('script')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--no-render', action='store_true')
    a = ap.parse_args()
    r = compile_script(Path(a.script), dry=a.dry, render=not a.no_render)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
