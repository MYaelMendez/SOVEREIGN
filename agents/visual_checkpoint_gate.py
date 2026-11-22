"""
visual_checkpoint_gate.py — close the visual grade into policy, veto-only.

An evidence grade is NOT authority. This gate is the bridge the recursive
learner asked for ("let the visual grade select or reject a checkpoint"), with
the authority direction corrected:

  a grade may REFUSE a checkpoint (fail-closed, evidence is sufficient);
  a grade may NEVER ACCEPT one — that requires a bound human grant.

Verbs
  doctor()                     measure the environment, never assert a capability
  grade(checkpoint, quality)   produce an evidence verdict from measured numbers
  gate(checkpoint, grade, approval=None)  decide: refuse / require_approval / accept
  grant(checkpoint)            report the required approval shape; grants:false
  ledger()                     hash-chained decisions (tamper detectable)

No credential, no secret, no self-grant. The approval's action_sha256 must equal
the checkpoint's own sha256 or the gate refuses — an approval for a different
checkpoint cannot be replayed onto this one.

Run:  python visual_checkpoint_gate.py doctor|grade|gate|grant|ledger
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

LEDGER = Path(os.environ.get(
    'CHECKPOINT_GATE_LEDGER',
    Path(os.environ.get('HERMES_HOME',
                        Path.home() / 'AppData/Local/hermes')) / 'checkpoint_gate.jsonl'))
GENESIS = '0' * 64

# thresholds are policy, not preference; changing one word changes the decision
THRESHOLDS = {'luminance': 20.0, 'contrast': 8.0, 'motion': 0.5,
              'black_pct_max': 0.01, 'mux_delta_max_s': 0.001}


def canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def checkpoint_sha(checkpoint: dict) -> str:
    """Contract read FROM the artifact fields, never from a name or docstring."""
    return sha(canon({k: checkpoint[k] for k in sorted(checkpoint)
                      if k in ('id', 'artifact', 'sha256', 'bytes')}))


def doctor() -> dict:
    return {'ok': True, 'ledger': str(LEDGER), 'ledger_exists': LEDGER.exists(),
            'thresholds': THRESHOLDS,
            'rule': 'a grade may refuse; only a bound human grant may accept'}


def grade(checkpoint: dict, quality: dict) -> dict:
    """Evidence verdict. Never carries authority."""
    fails = []
    for k, floor in (('luminance', THRESHOLDS['luminance']),
                     ('contrast', THRESHOLDS['contrast']),
                     ('motion', THRESHOLDS['motion'])):
        v = quality.get(k)
        if not isinstance(v, (int, float)) or v <= floor:
            fails.append(f'{k} missing or <= {floor}')
    if quality.get('black_pct', 1) > THRESHOLDS['black_pct_max']:
        fails.append('black_pct above max')
    if abs(quality.get('mux_delta_s', 999)) > THRESHOLDS['mux_delta_max_s']:
        fails.append('mux delta above max')
    return {'schema': 'ae/visual-grade/1', 'checkpoint_id': checkpoint.get('id'),
            'checkpoint_sha256': checkpoint_sha(checkpoint),
            'verdict': 'REFUSE' if fails else 'PASS', 'reasons': fails,
            'authority': 'none — evidence only'}


def grant(checkpoint: dict) -> dict:
    """Report the required approval shape. This NEVER grants anything."""
    return {'ok': False, 'grants': False, 'checkpoint_id': checkpoint.get('id'),
            'action_sha256': checkpoint_sha(checkpoint),
            'required': {'approval': {'human': True,
                                      'action_sha256': checkpoint_sha(checkpoint),
                                      'checkpoint_id': checkpoint.get('id')}},
            'rule': 'an address is not a permission; a passing grade is not an approval'}


def _read():
    if not LEDGER.exists():
        return []
    return [json.loads(l) for l in LEDGER.read_text(encoding='utf-8').splitlines()
            if l.strip()]


def receipt(decision: dict) -> dict:
    recs = _read()
    prev = recs[-1]['hash'] if recs else GENESIS
    r = dict(decision)
    r['prev'] = prev
    r['ts'] = time.time()
    r['hash'] = sha(canon({k: v for k, v in r.items() if k != 'hash'}))
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open('a', encoding='utf-8') as f:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
    return r


def gate(checkpoint: dict, quality: dict, approval: dict | None = None) -> dict:
    """Decide. Evidence can refuse; only a bound grant can accept."""
    g = grade(checkpoint, quality)
    if g['verdict'] == 'REFUSE':
        d = {'action': 'gate', 'decision': 'REFUSE', 'checkpoint_id': checkpoint.get('id'),
             'grade_sha256': sha(canon(g)), 'reasons': g['reasons'], 'granted': False}
        receipt(d)
        return {'ok': False, 'refused': True, 'decision': 'REFUSE',
                'reasons': g['reasons'], 'reason': 'visual grade failed — evidence refuses',
                'granted': False, 'grade': g}
    # grade passed — still require a human approval bound to THIS checkpoint
    ap = (approval or {}).get('approval', {})
    if not ap.get('human') or ap.get('action_sha256') != checkpoint_sha(checkpoint) \
            or ap.get('checkpoint_id') != checkpoint.get('id'):
        d = {'action': 'gate', 'decision': 'REQUIRE_APPROVAL',
             'checkpoint_id': checkpoint.get('id'), 'grade_sha256': sha(canon(g)),
             'granted': False}
        receipt(d)
        return {'ok': False, 'refused': True, 'decision': 'REQUIRE_APPROVAL',
                'reason': 'passing grade is evidence, not authority — human grant required',
                'granted': False, 'required': grant(checkpoint)['required'], 'grade': g}
    d = {'action': 'gate', 'decision': 'ACCEPT', 'checkpoint_id': checkpoint.get('id'),
         'grade_sha256': sha(canon(g)), 'granted': True,
         'approval_sha256': sha(canon(ap))}
    receipt(d)
    return {'ok': True, 'refused': False, 'decision': 'ACCEPT', 'granted': True,
            'reason': 'bound human approval present and checkpoint sha matches', 'grade': g}


def ledger() -> dict:
    recs = _read()
    prev = GENESIS
    for r in recs:
        body = {k: v for k, v in r.items() if k != 'hash'}
        if r.get('prev') != prev or r.get('hash') != sha(canon(body)):
            return {'ok': False, 'length': len(recs), 'reason': 'chain break'}
        prev = r['hash']
    return {'ok': True, 'length': len(recs), 'head': prev}


def main() -> int:
    ap = argparse.ArgumentParser(description='veto-only visual checkpoint gate')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor'); sub.add_parser('ledger')
    sub.add_parser('grant'); sub.add_parser('grade'); sub.add_parser('gate')
    a = ap.parse_args()
    ckpt = {'id': 'probe', 'artifact': 'probe.mp4', 'sha256': 'abc', 'bytes': 1}
    if a.cmd == 'doctor':
        r = doctor()
    elif a.cmd == 'ledger':
        r = ledger()
    elif a.cmd == 'grant':
        r = grant(ckpt)
    elif a.cmd == 'grade':
        r = grade(ckpt, {'luminance': 34.7, 'contrast': 38.49, 'motion': 3.383,
                         'black_pct': 0.0, 'mux_delta_s': 0.0})
    else:
        r = gate(ckpt, {'luminance': 34.7, 'contrast': 38.49, 'motion': 3.383,
                        'black_pct': 0.0, 'mux_delta_s': 0.0})
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r.get('ok', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
