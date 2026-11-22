#!/usr/bin/env python3
"""tinyLAB — the studio's recursive self-study.

The studio is a learning laboratory only if it learns about ITSELF. Every other
tiny* instrument measures something else: pixels, motion, time, a ledger, a
policy, a film. tinyLAB measures the laboratory, and feeds its own verdict back
as the next instruction.

    run → receipt → study (the lab grades itself) → change → next run

That is the recursion: the artefact of a run becomes the input of the next.

    tinylab instruments     the tiny* family present
    tinylab doctor          the lab's own state
    tinylab selftest [name] run the instruments' test suites
    tinylab study           the lab grades itself → ONE receipt
    tinylab next            the last study's `change` → the next brief
    tinylab ledger          the lab's hash chain

THE RULES (the same four, one level up)
  1. `doctor` measures the estate; it never asserts a capability.
  2. Every instrument must have a refusal path, and the tests must pin it.
  3. The ledger records DECISIONS; tamper must be detectable.
  4. The contract is read from the artifact — an instrument is what its tests
     and its refusals say it is, not what its name says.
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
sys.path.insert(0, str(ROOT))

LEDGER = Path(os.environ.get('TINYLAB_LEDGER',
                             Path(os.environ.get('HERMES_HOME',
                                                 Path.home() / 'AppData/Local/hermes'))
                             / 'tinylab.jsonl'))
GENESIS = '0' * 64

FAMILY = ['tinycuda', 'tinymujoco', 'tinycan', 'tinycudavideo', 'tinycontinuum',
          'tinyfilmmemory', 'tinyplugin', 'tinygpu', 'tinypython', 'tinypolicy',
          'tinyonnx', 'tinyvision', 'tinylab']


# ------------------------------------------------------------------ ledger
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


# ------------------------------------------------------------ inventory
def instruments() -> list[dict]:
    out = []
    for name in FAMILY:
        d = ROOT / name
        mod = d / f'{name}.py'
        tests = d / 'tests'
        n = len(list(tests.glob('test_*.py'))) if tests.exists() else 0
        cases = 0
        if tests.exists():
            r = subprocess.run([sys.executable, '-m', 'pytest', str(tests),
                                '--collect-only', '-q'],
                               capture_output=True, text=True)
            for line in (r.stdout or '').splitlines():
                if '::' in line:
                    cases += 1
                elif line.strip().endswith('tests collected') or 'test' in line.lower():
                    pass
        out.append({'name': name, 'module': mod.exists(), 'tests': n,
                    'cases': cases,
                    'readme': (d / 'README.md').exists()})
    return out


def doctor() -> dict:
    ins = instruments()
    present = [i for i in ins if i['module']]
    tested = [i for i in ins if i['cases'] > 0]
    untested = [i['name'] for i in ins if i['module'] and i['cases'] == 0]
    return {'ok': True, 'root': str(ROOT), 'family': len(FAMILY),
            'present': len(present), 'tested': len(tested),
            'untested': untested,
            'instruments': ins, 'ledger': ledger(),
            'why': 'the studio learns about itself: each run grades the last, '
                   'and the grade becomes the next instruction'}


# -------------------------------------------------------------- selftest
def selftest(name: str | None = None, timeout: int = 300) -> dict:
    """Run the instruments' test suites. A green suite is a measurement."""
    targets = [ROOT / name] if name else [ROOT / n for n in FAMILY]
    results = []
    for d in targets:
        t = d / 'tests'
        if not t.exists():
            results.append({'instrument': d.name, 'ran': False,
                            'reason': 'no tests directory'})
            continue
        try:
            r = subprocess.run([sys.executable, '-m', 'pytest', str(t), '-q',
                                '-p', 'no:cacheprovider'],
                               capture_output=True, text=True, timeout=timeout)
            tail = [l for l in (r.stdout or '').splitlines() if l.strip()][-1:]
            results.append({'instrument': d.name, 'ran': True,
                            'ok': r.returncode == 0, 'tail': tail[0] if tail else ''})
        except subprocess.TimeoutExpired:
            results.append({'instrument': d.name, 'ran': True, 'ok': False,
                            'reason': f'timeout after {timeout}s'})
    passed = sum(1 for r in results if r.get('ok'))
    rec = receipt('selftest', {'targets': [r['instrument'] for r in results],
                               'passed': passed, 'total': len(results)})
    return {'ok': passed == len([r for r in results if r.get('ran')]),
            'passed': passed, 'total': len(results), 'results': results,
            'ledger': rec['hash']}


# ---------------------------------------------------------------- study
def study() -> dict:
    """The lab grades itself. The receipt's `change` is the next instruction."""
    ins = instruments()
    d = doctor()
    st = selftest()
    tested = [i for i in ins if i['cases'] > 0]
    untested = [i['name'] for i in ins if i['module'] and i['cases'] == 0]
    # the recursion: what the last study asked for, and what this one changes
    last = None
    for r in reversed(_read()):
        if r.get('action') == 'study':
            last = r
            break
    prev_change = (last or {}).get('detail', {}).get('change')
    change = []
    if untested:
        change.append(f"give {', '.join(untested)} a refusal-pinned suite")
    if not st.get('ok'):
        change.append('repair the failing instrument suites')
    if not change:
        change.append('close the loop back into the policy: let the visual '
                      'grade select or reject a checkpoint')
    rec = receipt('study', {'present': d['present'], 'tested': len(tested),
                            'untested': untested, 'selftest_ok': st.get('ok'),
                            'passed': st.get('passed'), 'total': st.get('total'),
                            'prev_change': prev_change, 'change': change})
    return {'ok': bool(st.get('ok') and not untested),
            'instruments': d['present'], 'tested': len(tested),
            'untested': untested, 'selftest': {'passed': st.get('passed'),
                                               'total': st.get('total')},
            'prev_change': prev_change, 'change': change,
            'ledger': rec['hash'],
            'note': 'the artefact of a run becomes the input of the next'}


def next_brief() -> dict:
    """The last study's change → the next brief."""
    for r in reversed(_read()):
        if r.get('action') == 'study':
            return {'ok': True, 'brief': r['detail'].get('change'),
                    'from': r['hash'], 'note': 'the lab instructed itself'}
    return {'ok': False, 'reason': 'no study recorded yet'}


def main() -> int:
    ap = argparse.ArgumentParser(description='tinyLAB — the recursive self-study')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor'); sub.add_parser('ledger'); sub.add_parser('instruments')
    sub.add_parser('study'); sub.add_parser('next')
    p_st = sub.add_parser('selftest'); p_st.add_argument('name', nargs='?', default=None)
    a = ap.parse_args()
    if a.cmd == 'selftest':
        r = selftest(a.name)
    elif a.cmd == 'next':
        r = next_brief()
    elif a.cmd == 'instruments':
        r = {'ok': True, 'instruments': instruments()}
    else:
        r = globals()[a.cmd]()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r.get('ok', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
