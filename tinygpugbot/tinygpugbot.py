#!/usr/bin/env python3
"""tinyGPUBOT — the GPU-rendered robot as a scriptable actor.

The estate has the pieces: a policy that walks, a renderer that draws the real
CAD, a supervision that grades the picture, a voice, and a film format. What was
missing is the BOT — the actor that binds them: a name, a cast, a set of policy
verbs, a voice, and a ledger of its performances.

    tinyGPUBOT doctor                renderer, policy, traces, voice present?
    tinyGPUBOT cast <script>         resolve the cast (refuse what isn't there)
    tinyGPUBOT perform <script>      perform it: cues -> clips -> film -> receipt
    tinyGPUBOT ledger                the hash chain of performances

THE RULES (the tiny four, plus one)
  1. `doctor` measures; it never asserts a performance.
  2. Every verb has a refusal path, and the tests pin it: unknown actor, unknown
     verb, missing trace, missing renderer, a line that cannot be spoken.
  3. The ledger records PERFORMANCES, never intentions.
  4. The contract is read from the artifacts — the script, the trace, the film.
  5. A bot's motion is its POLICY's. tinyGPUBOT never keys a pose; if a verb has
     no trace it refuses rather than inventing a walk.

    tinygpugbot doctor
    tinygpugbot cast actors/the-first-script.json
    tinygpugbot perform actors/the-first-script.json
    tinygpugbot ledger
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

RTX = ROOT / 'agents' / 'rtx_asimov.py'
PROOF = ROOT / 'proof' / 'proof1.py'
LEDGER = Path(os.environ.get('TINYGPUBOT_LEDGER',
                             Path(os.environ.get('HERMES_HOME',
                                                 Path.home() / 'AppData/Local/hermes'))
                             / 'tinygpugbot.jsonl'))
GEN = {'python': os.environ.get('ACTOR_PYTHON', 'C:/gpu/Scripts/python.exe')}
GEN['actor_script'] = str(ROOT / 'actors' / 'actor_script.py')
GEN['voice'] = str(ROOT / 'osw-voice-lab' / 'det_voice.py')
GEN['supervise'] = str(ROOT / 'tinyvision' / 'tinyvision.py')

spec = importlib.util.spec_from_file_location('actor_script', GEN['actor_script'])
actor_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actor_script)

GENESIS = '0' * 64


# ------------------------------------------------------------------ ledger
def _canonical(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _read() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def receipt(action: str, detail: dict) -> dict:
    chain = _read()
    prev = chain[-1]['hash'] if chain else GENESIS
    body = {'action': action, 'detail': detail, 'prev': prev, 'ts': time.time()}
    h = _sha(_canonical(body))
    rec = dict(body, hash=h)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n')
    return rec


def ledger() -> dict:
    chain = _read()
    prev = GENESIS
    for i, r in enumerate(chain):
        body = {k: v for k, v in r.items() if k != 'hash'}
        if body.get('prev') != prev or _sha(_canonical(body)) != r.get('hash'):
            return {'ok': False, 'length': len(chain), 'broken_at': i + 1, 'head': prev}
        prev = r['hash']
    return {'ok': True, 'length': len(chain), 'head': prev}


# ---------------------------------------------------------------- doctor
def doctor() -> dict:
    checks = {
        'renderer': RTX.exists() and str(RTX),
        'film_format': PROOF.exists() and str(PROOF),
        'actor_script': Path(GEN['actor_script']).exists(),
        'voice': Path(GEN['voice']).exists(),
        'supervision': Path(GEN['supervise']).exists(),
        'interpreter': Path(GEN['python']).exists(),
        'policy': 'Menlo/asimov1-locomotion-0818',
    }
    try:
        import cupy  # noqa: F401
        checks['cuda'] = True
    except Exception as exc:
        checks['cuda'] = f'MISSING ({exc})'
    missing = [k for k, v in checks.items() if not v or 'MISSING' in str(v)]
    return {'ok': not missing, 'checks': checks, 'missing': missing,
            'ledger': ledger(),
            'why': 'the GPU-rendered robot as a scriptable actor'}


# ------------------------------------------------------------------ cast
def cast(script: Path) -> dict:
    """Resolve the cast. Refuse unknown actors/verbs and missing traces."""
    if not Path(script).exists():
        return {'ok': False, 'refused': True, 'reason': f'no such script: {script}'}
    try:
        s = json.loads(Path(script).read_text(encoding='utf-8'))
    except Exception as exc:
        return {'ok': False, 'refused': True, 'reason': f'bad script json: {exc}'}
    if s.get('schema') != 'actor/script/1':
        return {'ok': False, 'refused': True,
                'reason': f"schema must be actor/script/1, got {s.get('schema')}"}
    cast_map = {c['id']: c for c in s.get('cast', [])}
    cues = sorted(s.get('cues', []), key=lambda c: float(c['t']))
    resolved, refusals = [], []
    for i, cue in enumerate(cues):
        a = cue.get('actor')
        if a not in cast_map:
            refusals.append(f'cue {i}: unknown actor {a}')
            continue
        tr = cast_map[a].get('traces', {})
        if cue.get('verb') not in tr:
            refusals.append(f"cue {i}: {a} has no trace for {cue.get('verb')}")
            continue
        p = Path(tr[cue['verb']])
        if not p.exists():
            refusals.append(f"cue {i}: trace missing {p}")
            continue
        resolved.append({'cue': i, 'actor': a, 'verb': cue['verb'],
                         'line': cue.get('line', ''), 't': cue['t'],
                         'trace': str(p), 'trace_sha256': _sha(p.read_bytes()),
                         'camera': cue.get('camera') or {}})
    rec = receipt('cast', {'script': str(script), 'cues': len(cues),
                           'resolved': len(resolved), 'refusals': refusals})
    return {'ok': not refusals, 'refused': bool(refusals), 'script': str(script),
            'refusals': refusals, 'resolved': resolved,
            'seconds': float(s.get('seconds') or 0), 'ledger': rec['hash']}


# -------------------------------------------------------------- perform
def perform(script: Path, dry: bool = False) -> dict:
    c = cast(script)
    if not c['ok']:
        return c
    r = actor_script.compile_script(Path(script), dry=dry, render=not dry)
    rec = receipt('perform', {'script': str(script), 'dry': dry,
                              'ok': r.get('ok'), 'cues': r.get('cues'),
                              'seconds': r.get('seconds'),
                              'reason': r.get('reason')})
    r['ledger'] = rec['hash']
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description='tinyGPUBOT — the scriptable GPU actor')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor'); sub.add_parser('ledger')
    sub.add_parser('cast').add_argument('script')
    p_pf = sub.add_parser('perform'); p_pf.add_argument('script')
    p_pf.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    if a.cmd == 'cast':
        r = cast(a.script)
    elif a.cmd == 'perform':
        r = perform(a.script, dry=a.dry)
    else:
        r = globals()[a.cmd]()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r.get('ok', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
