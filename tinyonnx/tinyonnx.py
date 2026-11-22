#!/usr/bin/env python3
"""tinyONNX — the policy oracle for the tiny family.

Five Menlo policies exist; we were running one. tinyONNX is the instrument that
makes the set MEASURABLE: it reads the ONNX contract, refuses a policy that does
not match the viewer's 78-in / 23-out contract, rolls a policy out through the
pinned physics, grades the trace, and compares two policies on the same command.

    policy.onnx → inspect → contract → rollout → grade → receipt

It does not reimplement physics. `tinypython` owns the rollout; tinyONNX owns
the QUESTIONS about the policy:

  * what does this ONNX actually take and return?
  * does it match the viewer contract (78 in / 23 out)?
  * does it walk on a given command, and how far?
  * does policy A beat policy B on the same command?
  * is the run recorded, so the comparison is reproducible?

    tinyonnx doctor                 runtime + the policies present
    tinyonnx inspect <policy.onnx>  the I/O contract, from the file
    tinyonnx contract <policy.onnx> does it match 78/23?
    tinyonnx run <dir>              roll out a policy dir → trace + receipt
    tinyonnx grade <trace.json>     recompute the verdict from the trace
    tinyonnx compare <a> <b>        two policies, one command
    tinyonnx ledger                 the run hash chain

THE RULES
  1. The contract is read from the ONNX, never assumed.
  2. A policy that does not match the contract is REFUSED, not coerced.
  3. Grades are recomputed from the trace, never read from its success flag.
  4. Every run is a hash in the ledger; the ledger is a chain.
  5. Simulation only. A trace is a picture of a plan.
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

POLICIES = Path(os.environ.get('TINYONNX_POLICIES', HERE.parent / 'policies'))
LEDGER = Path(os.environ.get('TINYONNX_LEDGER',
                             Path(os.environ.get('HERMES_HOME',
                                                 Path.home() / 'AppData/Local/hermes'))
                             / 'tinyonnx.jsonl'))

# the viewer contract, verbatim from menloresearch/humanoid-policy-viewer
VIEWER_IN, VIEWER_OUT = 78, 23
POLICY_DT = 0.02
GENESIS = '0' * 64


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
    prev = GENESIS
    chain = _read()
    if chain:
        prev = chain[-1]['hash']
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
        body = {k: v for k, v in r.items() if k not in ('hash',)}
        if body.get('prev') != prev or _sha(_canonical(body)) != r.get('hash'):
            return {'ok': False, 'length': len(chain), 'broken_at': i + 1, 'head': prev}
        prev = r['hash']
    return {'ok': True, 'length': len(chain), 'head': prev}


# ---------------------------------------------------------------- inspect
def inspect(path: Path) -> dict:
    """Read the ONNX contract from the file. Never assume it."""
    p = Path(path)
    if not p.exists():
        return {'ok': False, 'refused': True, 'reason': f'no such policy: {p}'}
    try:
        import onnxruntime as ort
    except Exception as exc:
        return {'ok': False, 'refused': True, 'reason': f'onnxruntime unavailable: {exc}'}
    try:
        sess = ort.InferenceSession(str(p), providers=['CPUExecutionProvider'])
    except Exception as exc:
        return {'ok': False, 'refused': True, 'reason': f'not a loadable ONNX: {exc}'}
    b = p.read_bytes()
    return {'ok': True, 'path': str(p), 'sha256': _sha(b), 'bytes': len(b),
            'provider': 'CPUExecutionProvider',
            'inputs': [{'name': i.name, 'shape': list(i.shape), 'type': i.type}
                       for i in sess.get_inputs()],
            'outputs': [{'name': o.name, 'shape': list(o.shape), 'type': o.type}
                        for o in sess.get_outputs()]}


def contract(path: Path) -> dict:
    """Does the policy match the viewer contract? 78 in, 23 out."""
    r = inspect(path)
    if not r['ok']:
        return dict(r, contract_ok=False)
    ins = r['inputs'][0]['shape']
    outs = r['outputs'][0]['shape']
    last_in = ins[-1] if ins else None
    last_out = outs[-1] if outs else None
    ok = (last_in == VIEWER_IN and last_out == VIEWER_OUT)
    return {'ok': ok, 'path': str(path), 'sha256': r['sha256'],
            'expected': {'in': VIEWER_IN, 'out': VIEWER_OUT},
            'actual': {'in': last_in, 'out': last_out},
            'refused': not ok,
            'reason': None if ok else f'contract mismatch: {last_in} in / {last_out} out '
                                      f'(viewer wants {VIEWER_IN}/{VIEWER_OUT})'}


# ------------------------------------------------------------------- run
def run(policy_dir: Path, vx: float = 0.4, vy: float = 0.0, wz: float = 0.0,
        duration: float = 12.0, out: Path | None = None) -> dict:
    """Roll a policy out through the pinned physics. Simulation only."""
    import tinypython.tinypython as tp
    d = Path(policy_dir)
    pol = d / 'policy' / 'policy.onnx'
    c = contract(pol)
    if not c['ok']:
        receipt('run', {'policy': str(pol), 'refused': True,
                        'reason': c.get('reason')})
        return {'ok': False, 'refused': True, 'policy': str(pol),
                'reason': c.get('reason'), 'grants': False, 'executed': False}
    out = Path(out) if out else d / 'trace.json'
    os.environ['TINYPYTHON_ASSETS'] = str(d)
    r = tp.walk(out, vx=vx, vy=vy, wz=wz, duration=duration)
    r['policy_sha256'] = c['sha256']
    r['contract'] = {'in': c['actual']['in'], 'out': c['actual']['out']}
    rec = receipt('run', {'policy': str(pol), 'sha256': c['sha256'],
                          'vx': vx, 'vy': vy, 'wz': wz, 'duration': duration,
                          'ok': r.get('ok'), 'travel_x_m': r.get('base_x'),
                          'trace': str(out)})
    r['ledger'] = rec['hash']
    return r


def grade(trace_path: Path) -> dict:
    """Recompute the verdict from the trace."""
    import tinypython.tinypython as tp
    r = tp.verify(Path(trace_path))
    rec = receipt('grade', {'trace': str(trace_path), 'ok': r.get('ok'),
                            'travel_x_m': r.get('travel_x_m'),
                            'fell': r.get('fell')})
    r['ledger'] = rec['hash']
    return r


def compare(a: Path, b: Path, vx: float = 0.4, duration: float = 12.0) -> dict:
    """Two policies, one command. The comparison is only honest if both ran."""
    ra = run(a, vx=vx, duration=duration, out=Path(a) / 'compare.json')
    rb = run(b, vx=vx, duration=duration, out=Path(b) / 'compare.json')
    rec = receipt('compare', {'a': str(a), 'b': str(b), 'vx': vx,
                              'a_ok': ra.get('ok'), 'b_ok': rb.get('ok'),
                              'a_travel': ra.get('base_x'), 'b_travel': rb.get('base_x')})
    if not (ra.get('ok') and rb.get('ok')):
        return {'ok': False, 'refused': True,
                'reason': 'both policies must run to compare',
                'a': {'ok': ra.get('ok'), 'reason': ra.get('reason')},
                'b': {'ok': rb.get('ok'), 'reason': rb.get('reason')},
                'ledger': rec['hash']}
    ta, tb = float(ra['base_x']), float(rb['base_x'])
    return {'ok': True, 'command': {'vx': vx, 'duration': duration},
            'a': {'policy': str(a), 'sha256': ra['policy_sha256'],
                  'travel_x_m': ta, 'min_z_m': ra.get('min_z'),
                  'fell_at': ra.get('fell_at'), 'ticks': ra.get('ticks')},
            'b': {'policy': str(b), 'sha256': rb['policy_sha256'],
                  'travel_x_m': tb, 'min_z_m': rb.get('min_z'),
                  'fell_at': rb.get('fell_at'), 'ticks': rb.get('ticks')},
            'delta_m': round(ta - tb, 4), 'winner': ('a' if ta > tb else 'b' if tb > ta else 'tie'),
            'ledger': rec['hash'],
            'note': 'same command, same physics, same seed-free harness'}


def policies() -> list[dict]:
    out = []
    if not POLICIES.exists():
        return out
    for d in sorted(POLICIES.iterdir()):
        p = d / 'policy' / 'policy.onnx'
        if p.exists():
            c = contract(p)
            out.append({'dir': str(d), 'sha256': c.get('sha256'),
                        'contract_ok': c.get('ok'), 'reason': c.get('reason')})
    return out


def doctor() -> dict:
    try:
        import onnxruntime as ort
        rt = ort.__version__
    except Exception as exc:
        rt = f'MISSING ({exc})'
    pol = policies()
    return {'ok': rt != rt.startswith('MISSING') and 'MISSING' not in rt,
            'onnxruntime': rt, 'policies_dir': str(POLICIES),
            'count': len(pol), 'policies': pol, 'ledger': ledger(),
            'viewer_contract': {'in': VIEWER_IN, 'out': VIEWER_OUT},
            'deps': 'pip install onnxruntime (mujoco + numpy come with tinypython)',
            'why': 'five Menlo policies exist; this makes the set measurable'}


def main() -> int:
    ap = argparse.ArgumentParser(description='tinyONNX — the policy oracle')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor'); sub.add_parser('ledger'); sub.add_parser('policies')
    sub.add_parser('inspect').add_argument('policy')
    sub.add_parser('contract').add_argument('policy')
    p_run = sub.add_parser('run')
    p_run.add_argument('dir')
    p_run.add_argument('--vx', type=float, default=0.4)
    p_run.add_argument('--duration', type=float, default=12.0)
    p_run.add_argument('--out', default=None)
    sub.add_parser('grade').add_argument('trace')
    p_cmp = sub.add_parser('compare')
    p_cmp.add_argument('a'); p_cmp.add_argument('b')
    p_cmp.add_argument('--vx', type=float, default=0.4)
    a = ap.parse_args()
    if a.cmd == 'run':
        r = run(a.dir, vx=a.vx, duration=a.duration, out=a.out)
    elif a.cmd == 'compare':
        r = compare(a.a, a.b, vx=a.vx)
    elif a.cmd == 'grade':
        r = grade(a.trace)
    elif a.cmd == 'inspect':
        r = inspect(a.policy)
    elif a.cmd == 'contract':
        r = contract(a.policy)
    elif a.cmd == 'policies':
        r = {'ok': True, 'count': len(policies()), 'policies': policies()}
    else:
        r = globals()[a.cmd]()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r.get('ok', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
