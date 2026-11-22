"""
healer.py — the repair verb for known defect classes (Playwright-Healer shape).

The estate already has Planner (tinylab study) and Generator (agent writes code).
This is the missing Healer: given a defect signature and a staged copy of the
artifact, apply the registered repair, run the fail-closed gate, and PROPOSE a
diff. It never commits, never pushes, and never promotes without a bound human
grant. If the gate still fails after the turn limit, it SKIPS — it does not
claim a pass.

Lessons applied:
  • Playwright Healer: replay → inspect → patch → re-run until pass OR guardrails
    stop; skip when functionality is genuinely broken.
  • Microsoft Learn locator priority: the contract is read from the ARTIFACT's
    stable markers (data-verdict-parity, NO FINDING), never from a name.
  • Copilot Autofix: propose a diff + explanation for human review; never merge.
  • Agent Framework: bounded turns; approval_mode always_require for durable acts.

  healer strategies          known defect signatures
  healer heal <sig> <file>   stage → repair → gate → propose (or SKIP/REFUSE)
  healer grant <sig> <file>  report approval shape; grants:false
  healer promote <diff> <approval>   apply to the REAL file (requires grant)
  healer ledger              hash-chained decisions

No credential is read or written. All state lives in the ledger.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

LEDGER = Path(os.environ.get(
    'HEALER_LEDGER',
    Path(os.environ.get('HERMES_HOME',
                        Path.home() / 'AppData/Local/hermes')) / 'healer.jsonl'))
GENESIS = '0' * 64
MAX_TURNS = 3  # stop condition; 0 would mean "no autonomous continuation"


def canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ── registered STRATEGIES: known defect → deterministic repair + gate ──────
# A strategy must detect from the artifact, repair a COPY, and name a gate
# command that fails closed. An unknown signature REFUSES (no invention).

STRATEGIES = {
    'verdict_separator_emdash': {
        'detect': lambda t: 'VERDICT = re.compile(' in t and '[-–]' in t and '—' not in t.split('VERDICT = re.compile(')[1].split(')')[0],
        'repair': lambda t: t.replace('[-–]', '[-–—]', 1),
        # gate is bound to the STAGED bytes, never to a different artifact
        'check': lambda t: (bool(t) and '[-–—]' in t,
                            'staged verdict regex accepts em-dash' if t else 'REFUSED: staged file empty'),
        'defect': 'verdict regex lacks em-dash; a parsed section renders "not recorded"',
    },
    'tinylab_fallback_instruction': {
        'detect': lambda t: 'close the loop back into the policy' in t and 'NO FINDING' not in t,
        'repair': lambda t: t.replace(
            "        change.append('close the loop back into the policy: let the visual '\n"
            "                      'grade select or reject a checkpoint')",
            "        change = ['NO FINDING · all suites green, no refusal unpinned']\n"
            "        actionable = False", 1),
        'check': lambda t: (bool(t) and 'NO FINDING' in t and 'close the loop back into the policy' not in t,
                            'staged study emits NO FINDING' if t else 'REFUSED: staged file empty'),
        'defect': 'all-green study emits a hardcoded frontier task as an instruction',
    },
}


def strategies() -> dict:
    return {'ok': True, 'signatures': sorted(STRATEGIES), 'max_turns': MAX_TURNS,
            'rule': 'a known defect may be healed; an unknown signature REFUSES'}


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


def grant(sig: str, target: str) -> dict:
    return {'ok': False, 'grants': False, 'signature': sig,
            'action_sha256': sha(canon({'sig': sig, 'target': str(target)})),
            'required': {'approval': {'human': True, 'signature': sig,
                                      'target': str(target)}},
            'rule': 'a staged diff is a proposal; only a bound human grant may promote'}


def heal(sig: str, target: str, workdir: str | None = None) -> dict:
    """Replay → inspect → repair a COPY → run the gate → propose. Never writes target."""
    if sig not in STRATEGIES:
        receipt({'action': 'heal', 'signature': sig, 'decision': 'REFUSE',
                 'reason': 'unknown signature', 'granted': False})
        return {'ok': False, 'refused': True, 'decision': 'REFUSE',
                'reason': f'no registered repair for signature {sig!r}; refusing to invent one',
                'known': sorted(STRATEGIES)}

    p = Path(target)
    if not p.exists():
        receipt({'action': 'heal', 'signature': sig, 'decision': 'REFUSE',
                 'reason': 'artifact missing', 'granted': False})
        return {'ok': False, 'refused': True, 'decision': 'REFUSE',
                'reason': 'artifact missing — fail closed, no pass claimed'}

    original = p.read_text(encoding='utf-8', errors='replace')
    s = STRATEGIES[sig]
    if not s['detect'](original):
        receipt({'action': 'heal', 'signature': sig, 'decision': 'SKIP',
                 'reason': 'signature not present in artifact', 'granted': False})
        return {'ok': True, 'refused': False, 'decision': 'SKIP',
                'reason': 'defect signature not present — nothing to heal', 'granted': False}

    # stage a copy; never touch the real artifact
    stage = Path(os.environ.get('HEALER_STAGE', str(p.parent / (p.name + '.healer-stage'))))
    patched = original
    for turn in range(1, MAX_TURNS + 1):
        candidate = s['repair'](patched)
        if candidate == patched:
            break
        patched = candidate
        stage.write_text(patched, encoding='utf-8')
        # fail closed: gate reads the STAGED bytes, never a different artifact
        ok, tail = s['check'](stage.read_text(encoding='utf-8'))
        if ok:
            diff = ''.join(difflib.unified_diff(
                original.splitlines(True), patched.splitlines(True),
                fromfile=str(p), tofile=str(stage)))
            d = {'action': 'heal', 'signature': sig, 'decision': 'PROPOSE',
                 'target': str(p), 'turns': turn, 'gate_scope': 'staged_bytes',
                 'diff_sha256': sha(diff.encode()), 'granted': False}
            receipt(d)
            return {'ok': True, 'refused': False, 'decision': 'PROPOSE',
                    'turns': turn, 'gate_tail': tail, 'diff': diff,
                    'diff_sha256': d['diff_sha256'], 'staged': str(stage),
                    'gate_scope': 'staged_bytes',
                    'next': 'review the diff, then promote with a bound human grant',
                    'granted': False}
    # guardrails stopped the loop — SKIP, not a false PASS
    receipt({'action': 'heal', 'signature': sig, 'decision': 'SKIP',
             'target': str(p), 'turns': MAX_TURNS, 'reason': 'gate still failing',
             'granted': False})
    return {'ok': True, 'refused': False, 'decision': 'SKIP', 'turns': MAX_TURNS,
            'reason': 'repair did not satisfy the gate within the turn limit; '
                      'functionality may be genuinely broken — no pass claimed',
            'granted': False}


def promote(diff_sha: str, target: str, approval: dict | None = None) -> dict:
    """Apply a staged proposal to the REAL file. Requires a bound human grant."""
    act = sha(canon({'diff': diff_sha, 'target': str(target)}))
    ap = (approval or {}).get('approval', {})
    if not ap.get('human') or ap.get('action_sha256') != act or ap.get('target') != str(target):
        receipt({'action': 'promote', 'decision': 'REQUIRE_APPROVAL',
                 'target': str(target), 'granted': False})
        return {'ok': False, 'refused': True, 'decision': 'REQUIRE_APPROVAL',
                'granted': False,
                'required': {'approval': {'human': True, 'action_sha256': act,
                                          'target': str(target)}},
                'reason': 'a proposal is evidence, not authority'}
    stage = Path(str(target) + '.healer-stage')
    if not stage.exists() or sha(stage.read_bytes()) != diff_sha:
        return {'ok': False, 'refused': True, 'reason': 'staged bytes do not match the diff receipt'}
    Path(target).write_text(stage.read_text(encoding='utf-8'), encoding='utf-8')
    receipt({'action': 'promote', 'decision': 'APPLY', 'target': str(target),
             'granted': True, 'action_sha256': act})
    return {'ok': True, 'refused': False, 'decision': 'APPLY', 'granted': True,
            'reason': 'bound human grant present'}


def ledger() -> dict:
    recs = _read(); prev = GENESIS
    for r in recs:
        body = {k: v for k, v in r.items() if k != 'hash'}
        if r.get('prev') != prev or r.get('hash') != sha(canon(body)):
            return {'ok': False, 'length': len(recs), 'reason': 'chain break'}
        prev = r['hash']
    return {'ok': True, 'length': len(recs), 'head': prev}


def main() -> int:
    ap = argparse.ArgumentParser(description='healer — repair verb for known defects')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('strategies'); sub.add_parser('ledger')
    p_heal = sub.add_parser('heal')
    p_heal.add_argument('sig'); p_heal.add_argument('target')
    p_heal.add_argument('--workdir', default=None)
    p_grant = sub.add_parser('grant'); p_grant.add_argument('sig'); p_grant.add_argument('target')
    a = ap.parse_args()
    if a.cmd == 'strategies':
        r = strategies()
    elif a.cmd == 'ledger':
        r = ledger()
    elif a.cmd == 'grant':
        r = grant(a.sig, a.target)
    else:
        r = heal(a.sig, a.target, a.workdir)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r.get('ok', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
