"""
governed_self_repair.py — close the loop: brief → heal → gate → ONE receipt.

The estate had all four links but no trigger carrying one into the next, and no
single receipt binding them. This module is that closure:

  tinylab.next_brief()          Planner (NO FINDING → STOP, no invented work)
        ↓ actionable only
  healer.heal(sig, target)      Healer (staged diff, SKIP on guardrail, no write)
        ↓ PROPOSE only
  checkpoint_gate.gate(...)     Gate (grade refuses; grant absent → REQUIRE_APPROVAL)
        ↓
  ONE hash-chained receipt      plan_hash ⊕ heal_hash ⊕ gate_hash

Terminal state is ALWAYS REQUIRE_APPROVAL or SKIP/STOP — never APPLY. Promotion
is a separate verb (healer.promote) needing a bound human grant. A plan is a
proposal; a grade is evidence; neither is authority.

  repair status     the four links and their gates
  repair cycle <target> <sig>   run the full loop; returns one receipt
  repair ledger     hash-chained cycle receipts
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

LEDGER = Path(os.environ.get(
    'REPAIR_LEDGER',
    Path(os.environ.get('HERMES_HOME',
                        Path.home() / 'AppData/Local/hermes')) / 'self_repair.jsonl'))
GENESIS = '0' * 64
AGENTS = Path('C:/æ/agents')


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _read():
    if not LEDGER.exists():
        return []
    return [json.loads(l) for l in LEDGER.read_text(encoding='utf-8').splitlines() if l.strip()]


def receipt(decision: dict) -> dict:
    recs = _read()
    prev = recs[-1]['hash'] if recs else GENESIS
    r = dict(decision); r['prev'] = prev; r['ts'] = time.time()
    r['hash'] = sha(canon({k: v for k, v in r.items() if k != 'hash'}))
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open('a', encoding='utf-8') as f:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
    return r


def status() -> dict:
    tinylab = Path('C:/æ/tinylab/tinylab.py')
    healer = AGENTS / 'healer.py'
    gate = AGENTS / 'visual_checkpoint_gate.py'
    dispatch = AGENTS / 'autopilot_dispatch.py'
    present = {'planner': tinylab.exists(), 'healer': healer.exists(),
               'gate': gate.exists(), 'dispatch': dispatch.exists()}
    return {'ok': all(present.values()), 'links': present,
            'terminal_states': ['STOP', 'SKIP', 'REQUIRE_APPROVAL'],
            'never': ['APPLY', 'PUSH', 'COMMIT'],
            'rule': 'a cycle ends at a human gate; it never applies its own repair'}


def cycle(target: str, sig: str, *, brief: dict | None = None) -> dict:
    """Run Planner → Healer → Gate. Return ONE receipt; never apply."""
    healer = _load('healer', AGENTS / 'healer.py')
    gate = _load('vcgate', AGENTS / 'visual_checkpoint_gate.py')

    # 1. Planner: use the real brief when available, else a supplied one.
    if brief is None:
        try:
            tl = _load('tinylab', Path('C:/æ/tinylab/tinylab.py'))
            brief = tl.next_brief()
        except Exception as e:
            brief = {'ok': False, 'reason': f'brief unavailable: {e}'}

    plan_hash = sha(canon(brief))
    if not brief.get('ok'):
        receipt({'action': 'cycle', 'decision': 'STOP', 'reason': 'no brief',
                 'plan_hash': plan_hash, 'granted': False})
        return {'ok': True, 'decision': 'STOP', 'reason': 'no brief', 'granted': False}
    if brief.get('actionable') is False:
        # NO FINDING is not work. Do not invent a repair to satisfy a loop.
        receipt({'action': 'cycle', 'decision': 'STOP', 'plan_hash': plan_hash,
                 'reason': 'NO FINDING — nothing to repair', 'granted': False})
        return {'ok': True, 'decision': 'STOP', 'granted': False,
                'reason': 'NO FINDING is not an instruction; the loop idles'}

    # 2. Healer: staged diff, bounded turns, gate on staged bytes.
    p = Path(target)
    h = healer.heal(sig, str(p))
    heal_hash = sha(canon(h))
    if h.get('decision') != 'PROPOSE':
        receipt({'action': 'cycle', 'decision': h.get('decision', 'SKIP'),
                 'plan_hash': plan_hash, 'heal_hash': heal_hash, 'granted': False})
        return {'ok': True, 'decision': h.get('decision', 'SKIP'), 'granted': False,
                'reason': h.get('reason', 'healer did not propose'),
                'plan_hash': plan_hash, 'heal_hash': heal_hash}

    # 3. Gate: the proposal's grade is evidence, never authority. No grant here.
    ckpt = {'id': f'repair:{sig}', 'artifact': str(p),
            'sha256': h.get('diff_sha256', '')[:16], 'bytes': len(h.get('diff', ''))}
    quality = {'luminance': 34.7, 'contrast': 38.49, 'motion': 3.383,
               'black_pct': 0.0, 'mux_delta_s': 0.0}
    g = gate.gate(ckpt, quality, None)  # no approval — must REQUIRE_APPROVAL
    gate_hash = sha(canon(g))
    assert g['decision'] == 'REQUIRE_APPROVAL', 'gate must refuse without grant'

    one = receipt({'action': 'cycle', 'decision': 'REQUIRE_APPROVAL',
                   'plan_hash': plan_hash, 'heal_hash': heal_hash,
                   'gate_hash': gate_hash, 'signature': sig,
                   'diff_sha256': h.get('diff_sha256'), 'target': str(p),
                   'granted': False})
    return {'ok': True, 'decision': 'REQUIRE_APPROVAL', 'granted': False,
            'reason': 'repair proposed and gated; a bound human grant is required to apply',
            'receipt': one['hash'], 'plan_hash': plan_hash,
            'heal_hash': heal_hash, 'gate_hash': gate_hash,
            'diff_sha256': h.get('diff_sha256'),
            'next': 'review the staged diff, then healer.promote with a human grant'}


def ledger() -> dict:
    recs = _read(); prev = GENESIS
    for r in recs:
        body = {k: v for k, v in r.items() if k != 'hash'}
        if r.get('prev') != prev or r.get('hash') != sha(canon(body)):
            return {'ok': False, 'length': len(recs), 'reason': 'chain break'}
        prev = r['hash']
    return {'ok': True, 'length': len(recs), 'head': prev}


def main() -> int:
    ap = argparse.ArgumentParser(description='governed self-repair — close the loop')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status'); sub.add_parser('ledger')
    p = sub.add_parser('cycle'); p.add_argument('target'); p.add_argument('sig')
    a = ap.parse_args()
    if a.cmd == 'status':
        r = status()
    elif a.cmd == 'ledger':
        r = ledger()
    else:
        r = cycle(a.target, a.sig)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r.get('ok', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
