#!/usr/bin/env python3
"""tinyPOLICY — the robotics command-and-control for mobility.foundation.

The tiny family composes. tinycuda grades pixels, tinymujoco grades motion,
tinycan grades the bus, tinycudavideo grades the seam, tinycontinuum grades time,
tinyfilmmemory keeps the ledger. tinyPOLICY is the layer above them: the
COMMAND AND CONTROL of a mobility.foundation robot, where every request is a
PLAN, every motion is gated, and every decision leaves a hash.

    HUMAN://ROOT → æ POLICY → mobility.foundation → tinyPOLICY → RECEIPT

It does not invent motion. It composes what already exists:

    tinypython   the Menlo locomotion policy + physics + the deadman gate
    tinycuda     the pixels that prove the trace
    asimov://    the governed verb surface (same authority, same rules)

THE RULES (inherited, never relaxed)
  1. An address is not a permission. `plan` never connects.
  2. Motion requires a human: a FRESH presence AND a human signature.
     `presence` removes ONE refusal; it is never a signature.
  3. Never self-grant. `exec` returns `grants: false` unless a signature exists.
  4. A refusal is a result: `{"ok": false, "refused": true, ...}`.
  5. Simulation is always allowed — a trace is a picture of a plan.
  6. The ledger is a hash chain over the decisions, not over the intent.

    tinyPolicy doctor            policy, physics, deadman, ledger
    tinyPolicy status            the domain state
    tinyPolicy verbs             the verb surface with classes
    tinyPolicy plan walk         a plan, never an act
    tinyPolicy gate move         the deadman gate
    tinyPolicy trace out.json    run the policy walk (simulation)
    tinyPolicy verify out.json   did it walk, or fall?
    tinyPolicy exec stand        dry-run; motion is refused
    tinyPolicy ledger            the hash chain so far
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

DOMAIN = 'mobility.foundation'
SCHEMA = 'mobility.foundation/c2/1'
AUTHORITY = 'HUMAN://ROOT'
GENESIS = '0' * 64

try:
    import tinypython.tinypython as tp          # the policy + the deadman
except Exception:                              # pragma: no cover
    tp = None

LEDGER = Path(os.environ.get('TINYPOLICY_LEDGER',
                             Path(os.environ.get('HERMES_HOME',
                                                 Path.home() / 'AppData/Local/hermes'))
                             / 'tinypolicy.jsonl'))


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
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
    """Append a decision to the hash chain. Every verdict is a record."""
    prev = GENESIS
    chain = _read()
    if chain:
        prev = chain[-1]['hash']
    body = {'action': action, 'detail': detail, 'prev': prev, 'ts': time.time(),
            'domain': DOMAIN, 'authority': AUTHORITY}
    h = _sha(_canonical(body))
    rec = dict(body, hash=h, schema=SCHEMA)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n')
    return rec


def ledger() -> dict:
    chain = _read()
    prev = GENESIS
    for i, r in enumerate(chain):
        body = {k: v for k, v in r.items()
                if k not in ('hash', 'schema') and not k.startswith('_')}
        if body.get('prev') != prev or _sha(_canonical(body)) != r.get('hash'):
            return {'ok': False, 'length': len(chain), 'broken_at': i + 1,
                    'head': prev, 'domain': DOMAIN}
        prev = r['hash']
    return {'ok': True, 'length': len(chain), 'head': prev, 'domain': DOMAIN,
            'schema': SCHEMA}


# ---------------------------------------------------------------- verbs
VERBS = {
    'status':   {'class': 'read',    'needs': [],                   'note': 'domain state; sends nothing'},
    'verbs':    {'class': 'read',    'needs': [],                   'note': 'this surface'},
    'ledger':   {'class': 'read',    'needs': [],                   'note': 'the hash chain'},
    'doctor':   {'class': 'read',    'needs': [],                   'note': 'policy + physics + deadman'},
    'presence': {'class': 'read',    'needs': [],                   'note': 'is a human here right now'},
    'plan':     {'class': 'plan',    'needs': [],                   'note': 'a plan, never an act'},
    'trace':    {'class': 'simulate', 'needs': [],                  'note': 'run the policy walk; a picture of a plan'},
    'verify':   {'class': 'simulate', 'needs': [],                  'note': 'did it walk, or fall'},
    'arm':      {'class': 'control', 'needs': ['human'],            'note': 'record presence; not permission'},
    'disarm':   {'class': 'control', 'needs': ['human'],            'note': 'withdraw presence'},
    'gate':     {'class': 'control', 'needs': [],                   'note': 'evaluate the deadman'},
    'stand':    {'class': 'motion',  'needs': ['presence', 'signature'], 'note': 'refused without both'},
    'walk':     {'class': 'motion',  'needs': ['presence', 'signature'], 'note': 'refused without both'},
    'set_velocity': {'class': 'motion', 'needs': ['presence', 'signature'], 'note': 'refused'},
}


def verbs() -> dict:
    return {'ok': True, 'domain': DOMAIN, 'schema': SCHEMA, 'count': len(VERBS),
            'authority': AUTHORITY, 'verbs': VERBS,
            'note': 'no invented wire verbs; motion needs presence AND signature'}


def presence() -> dict:
    if tp is None:
        return {'present': False, 'reason': 'tinypython unavailable', 'grants': False}
    p = tp.presence()
    receipt('presence', {'present': p['present'], 'reason': p.get('reason')})
    return p


def plan(verb: str, **extra) -> dict:
    v = VERBS.get(verb)
    if not v:
        return {'ok': False, 'refused': True, 'reason': f'unknown verb: {verb}',
                'grants': False}
    rec = receipt('plan', {'verb': verb, 'class': v['class'], 'extra': extra})
    return {'ok': True, 'domain': DOMAIN, 'verb': verb, 'class': v['class'],
            'plan': {'action': verb, 'transport': 'none', 'connects': False},
            'executed': False, 'grants': False, 'receipt': rec['hash'],
            'note': 'an address is not a permission; a plan never connects'}


def gate(intent: str = 'move') -> dict:
    if tp is None:
        return {'ok': False, 'refused': True, 'reason': 'tinypython unavailable',
                'grants': False}
    g = tp.deadman_gate(intent)
    receipt('gate', {'intent': intent, 'decision': g['decision'],
                     'rules': g.get('rules'), 'presence': g.get('presence')})
    g['receipt'] = _read()[-1]['hash'] if _read() else None
    g['domain'] = DOMAIN
    return g


def exec(verb: str, **extra) -> dict:
    """Dry-run. Motion is refused: presence is not a signature."""
    v = VERBS.get(verb)
    if not v:
        return {'ok': False, 'refused': True, 'reason': f'unknown verb: {verb}',
                'grants': False}
    if v['class'] == 'motion':
        g = gate(verb)
        rec = receipt('exec', {'verb': verb, 'class': v['class'],
                               'decision': 'refused', 'rules': g.get('rules')})
        return {'ok': False, 'refused': True, 'verb': verb, 'class': v['class'],
                'decision': 'require_approval', 'rules': g.get('rules'),
                'presence': g.get('presence'), 'grants': False, 'executed': False,
                'receipt': rec['hash'],
                'reason': 'motion needs a fresh presence AND a human signature'}
    if v['class'] == 'simulate':
        return {'ok': True, 'verb': verb, 'class': v['class'], 'executed': False,
                'grants': False,
                'note': 'simulation is allowed; a trace is a picture of a plan'}
    rec = receipt('exec', {'verb': verb, 'class': v['class']})
    return {'ok': True, 'verb': verb, 'class': v['class'], 'executed': False,
            'grants': False, 'receipt': rec['hash']}


def trace(out: Path, vx: float = 0.4, duration: float = 12.0) -> dict:
    """Run the policy walk. Simulation: always allowed."""
    if tp is None:
        return {'ok': False, 'refused': True, 'reason': 'tinypython unavailable'}
    r = tp.walk(Path(out), vx=vx, duration=duration)
    receipt('trace', {'out': str(out), 'vx': vx, 'duration': duration,
                      'ok': r.get('ok')})
    return r


def verify(trace_path: Path) -> dict:
    if tp is None:
        return {'ok': False, 'refused': True, 'reason': 'tinypython unavailable'}
    r = tp.verify(Path(trace_path))
    receipt('verify', {'trace': str(trace_path), 'walked': r.get('ok'),
                       'reason': r.get('reason')})
    return r


def status() -> dict:
    p = tp.presence() if tp else {'present': False, 'reason': 'unavailable'}
    lg = ledger()
    return {'ok': True, 'domain': DOMAIN, 'schema': SCHEMA, 'authority': AUTHORITY,
            'policy': (tp.doctor() if tp else {'ok': False}),
            'presence': p, 'ledger': lg,
            'verbs': len(VERBS),
            'note': 'a simulation domain; no hardware is commanded here'}


def doctor() -> dict:
    d = {'ok': tp is not None, 'domain': DOMAIN, 'schema': SCHEMA,
         'deps': 'tinypython (policy+physics+deadman)', 'tokens': 0,
         'policy': (tp.doctor() if tp else None),
         'ledger': ledger(),
         'presence': (tp.presence() if tp else None),
         'why': 'the command layer over the tiny family: every request a plan, '
                'every motion gated, every decision a hash'}
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description='tinyPOLICY — mobility.foundation C2')
    sub = ap.add_subparsers(dest='cmd', required=True)
    for c in ('doctor', 'status', 'verbs', 'ledger', 'presence'):
        sub.add_parser(c)
    sub.add_parser('plan').add_argument('verb')
    sub.add_parser('gate').add_argument('intent', nargs='?', default='move')
    sub.add_parser('exec').add_argument('verb')
    sub.add_parser('trace').add_argument('out')
    sub.add_parser('verify').add_argument('trace')
    a = ap.parse_args()
    if a.cmd == 'trace':
        r = trace(a.out)
    elif a.cmd == 'verify':
        r = verify(a.trace)
    elif a.cmd == 'plan':
        r = plan(a.verb)
    elif a.cmd == 'gate':
        r = gate(a.intent)
    elif a.cmd == 'exec':
        r = exec(a.verb)
    elif a.cmd == 'ledger':
        r = ledger()
    elif a.cmd == 'presence':
        r = presence()
    else:
        r = globals()[a.cmd]()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r.get('ok', r.get('present')) else 1


if __name__ == '__main__':
    raise SystemExit(main())
