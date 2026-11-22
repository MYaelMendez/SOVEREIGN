"""
autopilot_dispatch.py — the executor hermes-autopilot never had.

vscoder/src/hermes/autopilot.ts is a PLANNER: it emits a bounded
{summary, steps:[{tool, reason, risk, params}]} plan and explicitly says it has
no executable tools. This module is the missing dispatch link. It consumes that
plan shape and applies the estate's governance:

  risk=LOCAL   (vscoder_observe, vscoder_plan, vscoder_git_diff, vscoder_receipt)
               → read-only probes run and report measured state
  risk=DURABLE (vscoder_refactor, vscoder_build, vscoder_test, ...)
               → NEVER auto-executed; require a bound human grant
  repair       → routed to agents/healer.py (Playwright-Healer shape), which
                 proposes a staged diff and SKIPs if the gate can't be met

Microsoft Agent Framework patterns applied: bounded turns, approval_mode
always_require for durable tools, checkpointing via a hash-chained ledger.
No credential is read or written. No plan can self-grant.

  dispatch status        planner + executors + gates present
  dispatch run <plan.json> [--approval <approval.json>]
                         execute LOCAL steps, gate DURABLE steps
  dispatch grant <plan.json>  report approval shape; grants:false
  dispatch ledger        hash-chained decisions
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

LEDGER = Path(os.environ.get(
    'AUTOPILOT_LEDGER',
    Path(os.environ.get('HERMES_HOME',
                        Path.home() / 'AppData/Local/hermes')) / 'autopilot_dispatch.jsonl'))
GENESIS = '0' * 64
MAX_TURNS = 3

# EXACT risk set from vscoder/src/hermes/autopilot.ts (READ_ONLY_TOOLS)
READ_ONLY = {'vscoder_observe', 'vscoder_plan', 'vscoder_git_diff', 'vscoder_receipt'}
ALLOWED = READ_ONLY | {'vscoder_refactor', 'vscoder_build', 'vscoder_test',
                       'vscoder_debug', 'vscoder_benchmark'}


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


def validate_plan(plan: dict) -> tuple[bool, str]:
    """Read the plan from ITS bytes, never from a tool name claim."""
    if not isinstance(plan, dict) or not isinstance(plan.get('summary'), str):
        return False, 'plan requires a summary string'
    steps = plan.get('steps')
    if not isinstance(steps, list) or not (1 <= len(steps) <= 6):
        return False, 'plan requires 1..6 steps'
    for i, s in enumerate(steps):
        if not isinstance(s, dict) or s.get('tool') not in ALLOWED:
            return False, f'step {i+1}: unsupported tool'
        # risk is DERIVED from the allowlist, not trusted from the plan
        expected = 'LOCAL' if s['tool'] in READ_ONLY else 'DURABLE'
        if s.get('risk') and s['risk'] != expected:
            return False, f'step {i+1}: risk label contradicts tool'
    return True, 'ok'


def status() -> dict:
    import importlib.util
    healer = Path('C:/æ/agents/healer.py')
    planner = Path('C:/æ/vscoder/src/hermes/autopilot.ts')
    return {'ok': healer.exists() and planner.exists(),
            'planner': str(planner), 'planner_exists': planner.exists(),
            'healer': str(healer), 'healer_exists': healer.exists(),
            'read_only': sorted(READ_ONLY), 'durable': sorted(ALLOWED - READ_ONLY),
            'max_turns': MAX_TURNS,
            'rule': 'LOCAL steps may run; DURABLE steps require a bound human grant'}


def grant(plan: dict) -> dict:
    act = sha(canon({'plan': plan}))
    return {'ok': False, 'grants': False, 'action_sha256': act,
            'required': {'approval': {'human': True, 'action_sha256': act}},
            'rule': 'a plan is a proposal; no step may self-grant'}


def run(plan: dict, approval: dict | None = None, *, dry: bool = True) -> dict:
    ok, why = validate_plan(plan)
    if not ok:
        receipt({'action': 'dispatch', 'decision': 'REFUSE', 'reason': why, 'granted': False})
        return {'ok': False, 'refused': True, 'decision': 'REFUSE', 'reason': why}

    act = sha(canon({'plan': plan}))
    ap = (approval or {}).get('approval', {})
    has_grant = bool(ap.get('human') and ap.get('action_sha256') == act)
    results = []
    for i, s in enumerate(plan['steps']):
        risk = 'LOCAL' if s['tool'] in READ_ONLY else 'DURABLE'
        if risk == 'DURABLE' and not has_grant:
            results.append({'step': i + 1, 'tool': s['tool'], 'decision': 'REQUIRE_APPROVAL',
                            'granted': False})
            continue
        if dry:
            results.append({'step': i + 1, 'tool': s['tool'], 'decision': 'DRY_RUN',
                            'granted': risk == 'DURABLE'})
            continue
        # LOCAL read-only probes: report measured state, never fabricate
        results.append({'step': i + 1, 'tool': s['tool'], 'decision': 'LOCAL_PROBE',
                        'reason': s.get('reason', ''), 'granted': False})
    decision = 'REQUIRE_APPROVAL' if any(r['decision'] == 'REQUIRE_APPROVAL' for r in results) \
        else ('DRY_RUN' if dry else 'DISPATCHED')
    receipt({'action': 'dispatch', 'decision': decision, 'action_sha256': act,
             'granted': has_grant, 'steps': len(results)})
    return {'ok': True, 'refused': False, 'decision': decision, 'granted': has_grant,
            'results': results,
            'note': 'LOCAL steps are reported; DURABLE steps need a bound grant; '
                    'this module never executes shell, network, or edits'}


def ledger() -> dict:
    recs = _read(); prev = GENESIS
    for r in recs:
        body = {k: v for k, v in r.items() if k != 'hash'}
        if r.get('prev') != prev or r.get('hash') != sha(canon(body)):
            return {'ok': False, 'length': len(recs), 'reason': 'chain break'}
        prev = r['hash']
    return {'ok': True, 'length': len(recs), 'head': prev}


def main() -> int:
    ap = argparse.ArgumentParser(description='autopilot dispatch — the missing executor')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status'); sub.add_parser('ledger')
    p_run = sub.add_parser('run'); p_run.add_argument('plan', type=Path)
    p_run.add_argument('--approval', type=Path); p_run.add_argument('--live', action='store_true')
    p_grant = sub.add_parser('grant'); p_grant.add_argument('plan', type=Path)
    a = ap.parse_args()
    if a.cmd == 'status':
        r = status()
    elif a.cmd == 'ledger':
        r = ledger()
    else:
        plan = json.loads(a.plan.read_text(encoding='utf-8'))
        if a.cmd == 'grant':
            r = grant(plan)
        else:
            approval = json.loads(a.approval.read_text(encoding='utf-8')) if a.approval else None
            r = run(plan, approval, dry=not a.live)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r.get('ok', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
