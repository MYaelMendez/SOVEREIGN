#!/usr/bin/env python3
"""
tinyACTOR Task 4 — director's cue sheet / receipted take.

A TAKE is a human-directed unit of film: {scene, verb, args, grant_sha,
start, end, camera}. It is recorded ONLY when a bound card verifies for the
EXACT action. Takes never auto-chain: a second take on one card is REFUSED.

This module does NOT grant, does NOT move hardware, and does NOT choose a cast.
Without a bound operator it returns explicit refusals — never a stub take.
"""
from __future__ import annotations

import hashlib, importlib.util, json, os, time
from pathlib import Path

OPERATOR = Path('C:/æ/agents/tinyactor_operator.py')
LEDGER = Path(os.environ.get('TINYACTOR_TAKES', 'C:/æ/logs/tinyactor-takes.jsonl'))
GENESIS = '0' * 64


def _mod(path, name):
    s = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


# Single source of the operator gate. Tests can inject a module (with a patched
# BINDING) here; re-importing on every call silently bypassed that injection.
OPERATOR_MOD = None


def operator_mod():
    global OPERATOR_MOD
    if OPERATOR_MOD is None:
        OPERATOR_MOD = _mod(OPERATOR, 'tinyactor_operator_for_take')
    return OPERATOR_MOD


def canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_takes() -> list:
    if not LEDGER.exists():
        return []
    return [json.loads(l) for l in LEDGER.read_text(encoding='utf-8').splitlines() if l.strip()]


def verify_chain(recs: list) -> bool:
    prev = GENESIS
    for r in recs:
        body = {k: v for k, v in r.items() if k != 'hash'}
        if r.get('prev') != prev or r.get('hash') != sha(canon(body)):
            return False
        prev = r['hash']
    return True


def _action_for(take: dict) -> dict:
    """The exact action a card must be bound to for this take."""
    return {'verb': take['verb'], 'args': take['args'], 'scene': take['scene']}


def record(take: dict, card: dict | None = None) -> dict:
    """Record one human-directed take. Refuse unless a bound card verifies."""
    op = operator_mod()
    st = op.status()
    if not st['bound']:
        return {'ok': True, 'refused': True, 'decision': 'REFUSE',
                'reason': st.get('reason', 'operator not bound'),
                'granted': False, 'grants': False, 'recorded': False}
    required = ('scene', 'verb', 'args', 'start', 'end', 'camera')
    missing = [k for k in required if k not in take]
    if missing:
        return {'ok': True, 'refused': True, 'decision': 'REFUSE',
                'reason': 'take incomplete: ' + ', '.join(missing),
                'granted': False, 'grants': False, 'recorded': False}
    if not card:
        return {'ok': True, 'refused': True, 'decision': 'REFUSE',
                'reason': 'take requires a bound card',
                'granted': False, 'grants': False, 'recorded': False}
    action = _action_for(take)
    v = op.verify(card, action)
    if not v.get('valid'):
        return {'ok': True, 'refused': True, 'decision': 'REFUSE',
                'reason': v.get('reason', 'card not valid for this action'),
                'granted': False, 'grants': False, 'recorded': False}
    # Explicit take-level replay guard: one card, one take, always.
    card_hash = sha(canon(card))
    if any(t.get('card_sha256') == card_hash for t in read_takes()):
        return {'ok': True, 'refused': True, 'decision': 'REFUSE',
                'reason': 'card already used for a take — no auto-chaining',
                'granted': False, 'grants': False, 'recorded': False}
    recs = read_takes()
    prev = recs[-1]['hash'] if recs else GENESIS
    row = {'schema': 'ae/tinyactor-take/1', 'ts': time.time(),
           'scene': take['scene'], 'verb': take['verb'], 'args': take['args'],
           'start': take['start'], 'end': take['end'], 'camera': take['camera'],
           'action_sha256': sha(canon(action)), 'card_sha256': card_hash,
           'granted': False, 'grants': False, 'prev': prev}
    row['hash'] = sha(canon(row))
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
    return {'ok': True, 'refused': False, 'decision': 'RECORDED',
            'granted': False, 'grants': False, 'recorded': True,
            'take_sha256': row['hash'], 'ledger': str(LEDGER)}


def status() -> dict:
    recs = read_takes()
    return {'ok': True, 'count': len(recs), 'chain_ok': verify_chain(recs),
            'head': recs[-1]['hash'] if recs else GENESIS,
            'note': 'no cast is chosen here; each take needs its own bound card'}
