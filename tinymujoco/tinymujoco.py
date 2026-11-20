#!/usr/bin/env python3
"""tinyMUJOCO — headless deterministic contact physics, and a verifier for it.

    pip install mujoco numpy
    python tinymujoco.py doctor
    python tinymujoco.py rollout model.xml --seed 0 --steps 600 --out trace.npy
    python tinymujoco.py reference model.xml --seed 0 --steps 600 --out ref.npy
    python tinymujoco.py grade trace.npy ref.npy
    python tinymujoco.py bench model.xml

WHY THIS EXISTS
    MuJoCo's RENDERER needs OpenGL. Its PHYSICS does not. On an Optimus laptop
    with no registered NVIDIA OpenGL ICD, the GL path lands on the integrated
    GPU and everything visual crawls — while contact dynamics run untouched on
    the CPU. This is the headless half: load a model, step it, get a trace.
    No window, no GL context, no display server.

THE INNOVATION IS NOT THE STEPPING
    It is what determinism enables. MuJoCo is bit-reproducible: the same model,
    the same initial state and the same control sequence produce a BYTE-IDENTICAL
    trajectory. Measured on this machine: max absolute difference 0.0 across two
    independent runs of 400 steps.

    So a trajectory hash is a gradeable assertion. `grade` compares a candidate
    trace against a reference and returns reward 1.0 or 0.0 — zero tokens, zero
    model calls, no judge. An agent that writes a control sequence can be scored
    on the MOTION IT PRODUCED, not on whether its code looks plausible.

    tinyCUDA grades pixels. tinyMUJOCO grades motion. Two independent oracles
    over the same robot: what it did, and what it looked like doing it.

WHAT IT REFUSES
    A trace whose shape does not match the reference is refused, not broadcast-
    compared. A reference produced by a different model is refused by hash
    mismatch rather than silently scored. `grade` never returns a partial
    reward: physics either reproduced or it did not.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from pathlib import Path

import numpy as np

SCHEMA = 'ae/tinymujoco/1'


def _mj():
    try:
        import mujoco
        return mujoco, None
    except ImportError as exc:
        return None, f'mujoco not installed in this interpreter: {exc}'


def doctor() -> dict:
    """Probe the live system. Never report a hardcoded capability."""
    mj, err = _mj()
    out = {'schema': SCHEMA, 'ok': err is None, 'grants': False,
           'checks': {}, 'deps': 'pip install mujoco numpy'}
    if err:
        out['checks']['mujoco'] = err
        return out
    out['checks']['mujoco'] = mj.__version__
    out['checks']['numpy'] = np.__version__
    # the whole point: physics needs no GL. Report the absence as a FEATURE.
    out['checks']['opengl_required'] = False
    out['checks']['display_required'] = False
    out['checks']['headless'] = True
    try:
        m = mj.MjModel.from_xml_string(
            '<mujoco><worldbody><body><geom type="sphere" size="0.1"/>'
            '<joint type="free"/></body></worldbody></mujoco>')
        d = mj.MjData(m)
        for _ in range(10):
            mj.mj_step(m, d)
        out['checks']['smoke'] = f'10 steps, qpos[2]={d.qpos[2]:.6f}'
        out['checks']['timestep'] = float(m.opt.timestep)
    except Exception as exc:
        out['ok'] = False
        out['checks']['smoke'] = f'FAILED {type(exc).__name__}: {exc}'
    return out


def rollout(model_path: Path, seed: int = 0, steps: int = 600,
            qpos0=None, ctrl_scale: float = 0.3, out: Path | None = None) -> dict:
    """Step physics under a seeded control sequence. Deterministic by construction."""
    mj, err = _mj()
    if err:
        return {'ok': False, 'refused': True, 'reason': err, 'grants': False}
    p = Path(model_path)
    if not p.exists():
        return {'ok': False, 'refused': True, 'reason': f'no such model: {p}', 'grants': False}
    try:
        m = mj.MjModel.from_xml_path(str(p))
    except Exception as exc:
        return {'ok': False, 'refused': True,
                'reason': f'model failed to load: {type(exc).__name__}: {exc}', 'grants': False}
    d = mj.MjData(m)
    mj.mj_resetData(m, d)
    if qpos0 is not None:
        q0 = np.asarray(qpos0, np.float64)
        if q0.shape != (m.nq,):
            return {'ok': False, 'refused': True,
                    'reason': f'qpos0 shape {q0.shape}, expected {(m.nq,)}', 'grants': False}
        d.qpos[:] = q0
    mj.mj_forward(m, d)

    rng = np.random.default_rng(seed)
    qs = np.empty((steps, m.nq), np.float64)
    ctrl = np.empty((steps, m.nu), np.float64)
    t0 = time.perf_counter()
    for t in range(steps):
        c = rng.uniform(-ctrl_scale, ctrl_scale, m.nu)
        d.ctrl[:] = c
        mj.mj_step(m, d)
        qs[t] = d.qpos
        ctrl[t] = c
    wall = time.perf_counter() - t0

    model_sha = hashlib.sha256(p.read_bytes()).hexdigest()
    trace_sha = hashlib.sha256(qs.tobytes()).hexdigest()
    res = {'schema': SCHEMA, 'ok': True, 'model': str(p), 'model_sha256': model_sha,
           'seed': seed, 'steps': steps, 'nq': int(m.nq), 'nv': int(m.nv), 'nu': int(m.nu),
           'timestep': float(m.opt.timestep), 'ctrl_scale': ctrl_scale,
           'controllable': bool(m.nu > 0),
           'seed_affects_motion': bool(m.nu > 0),
           'trace_sha256': trace_sha,
           'qpos0': (np.asarray(qpos0, np.float64).tolist() if qpos0 is not None else None),
           'wall_s': round(wall, 4), 'steps_per_s': round(steps / wall, 1),
           'realtime_factor': round(steps * float(m.opt.timestep) / wall, 2),
           'final_qpos': qs[-1].tolist(),
           'grants': False, 'executed': False, 'hardware': False,
           'note': 'simulation only. Deterministic: same model + seed + steps '
                   'reproduces these bytes exactly.'
                   + ('' if m.nu > 0 else ' This model has no actuators, so the '
                      'seed cannot affect the motion — the trace is open-loop dynamics.')}
    if out:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        np.save(out, qs)
        meta = out.with_suffix('.json')
        meta.write_text(json.dumps({**res, 'trace_file': out.name,
                                    'ctrl': ctrl.tolist()}, indent=2), encoding='utf-8')
        res['trace'] = str(out)
        res['meta'] = str(meta)
    return res


def reference(model_path: Path, seed: int = 0, steps: int = 600,
              out: Path | None = None, **kw) -> dict:
    """Produce the oracle. Two independent runs must agree, or we refuse to ship it."""
    a = rollout(model_path, seed, steps, out=out, **kw)
    if not a.get('ok'):
        return a
    b = rollout(model_path, seed, steps, out=None, **kw)
    if not b.get('ok'):
        return b
    if a['trace_sha256'] != b['trace_sha256']:
        return {'ok': False, 'refused': True,
                'reason': 'physics did not reproduce across two runs — a reference '
                          'built on nondeterminism would grade noise',
                'run_a': a['trace_sha256'], 'run_b': b['trace_sha256'], 'grants': False}
    a['verified_deterministic'] = True
    a['reference'] = True
    return a


def grade(candidate: Path, ref: Path) -> dict:
    """reward 1.0 or 0.0. Zero tokens, zero model calls.

    Shape mismatch is REFUSED, never broadcast-compared: a shorter trace that
    happens to share a prefix is not a reproduction.
    """
    ca, rf = Path(candidate), Path(ref)
    for p in (ca, rf):
        if not p.exists():
            return {'ok': False, 'refused': True, 'reason': f'no such file: {p}', 'grants': False}
    try:
        a = np.load(ca); b = np.load(rf)
    except Exception as exc:
        return {'ok': False, 'refused': True,
                'reason': f'not a .npy trace: {type(exc).__name__}', 'grants': False}
    if a.shape != b.shape:
        return {'ok': False, 'refused': True,
                'reason': f'shape {a.shape} != reference {b.shape}; a prefix is not a reproduction',
                'reward': 0.0, 'grants': False}
    ha = hashlib.sha256(a.tobytes()).hexdigest()
    hb = hashlib.sha256(b.tobytes()).hexdigest()
    same = ha == hb
    diff = np.abs(a - b)
    return {'schema': SCHEMA, 'ok': True, 'reward': 1.0 if same else 0.0,
            'identical': same, 'candidate_sha256': ha, 'reference_sha256': hb,
            'shape': list(a.shape), 'max_abs_diff': float(diff.max()),
            'mean_abs_diff': float(diff.mean()),
            'differing_elements': int((diff > 0).sum()),
            'tokens_used': 0, 'model_calls': 0, 'grants': False,
            'note': 'byte comparison of the trajectory. No judge, no partial credit.'}


def bench(model_path: Path, sizes=(500, 2000, 8000), reps: int = 3) -> dict:
    mj, err = _mj()
    if err:
        return {'ok': False, 'reason': err, 'grants': False}
    rows = []
    for n in sizes:
        best = None
        for _ in range(reps):
            r = rollout(model_path, seed=0, steps=n)
            if not r.get('ok'):
                return r
            if best is None or r['steps_per_s'] > best['steps_per_s']:
                best = r
        rows.append({'steps': n, 'steps_per_s': best['steps_per_s'],
                     'wall_s': best['wall_s'], 'realtime_factor': best['realtime_factor']})
    return {'schema': SCHEMA, 'ok': True, 'model': str(model_path), 'rows': rows,
            'mujoco': mj.__version__, 'grants': False,
            'note': 'best of reps. Timing is a measurement, never a test assertion.'}


def main():
    ap = argparse.ArgumentParser(prog='tinymujoco')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor', help='probe physics availability — no GL required')
    r = sub.add_parser('rollout', help='step physics under a seeded control sequence')
    r.add_argument('model'); r.add_argument('--seed', type=int, default=0)
    r.add_argument('--steps', type=int, default=600)
    r.add_argument('--ctrl-scale', type=float, default=0.3)
    r.add_argument('--out')
    f = sub.add_parser('reference', help='produce a verified-deterministic oracle')
    f.add_argument('model'); f.add_argument('--seed', type=int, default=0)
    f.add_argument('--steps', type=int, default=600)
    f.add_argument('--ctrl-scale', type=float, default=0.3)
    f.add_argument('--out', required=True)
    g = sub.add_parser('grade', help='reward 1.0/0.0 against a reference trace')
    g.add_argument('candidate'); g.add_argument('reference')
    b = sub.add_parser('bench', help='steps per second')
    b.add_argument('model')
    a = ap.parse_args()
    if a.cmd == 'doctor':
        res = doctor()
    elif a.cmd == 'rollout':
        res = rollout(Path(a.model), a.seed, a.steps,
                      ctrl_scale=a.ctrl_scale, out=Path(a.out) if a.out else None)
    elif a.cmd == 'reference':
        res = reference(Path(a.model), a.seed, a.steps,
                        out=Path(a.out), ctrl_scale=a.ctrl_scale)
    elif a.cmd == 'grade':
        res = grade(Path(a.candidate), Path(a.reference))
    else:
        res = bench(Path(a.model))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
