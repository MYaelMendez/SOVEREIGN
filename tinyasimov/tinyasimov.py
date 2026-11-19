#!/usr/bin/env python3
"""tinyASIMOV — the whole robot, composed.

Four small routes, one machine, no cloud:

    tiny-voca    voice     4.5M params, CPU
    tinyCUDA     pixels    ~300 lines, CUDA, deterministic
    tinyGPU      body      527 lines, real Menlo CAD
    tinyPython   motion    ~330 lines, policy-driven, CPU

tinyASIMOV is not a fifth capability. It is the **composition** — the thing
that makes the four addressable as one robot, under one gate.

    tinyasimov doctor          every link, measured
    tinyasimov status          what the robot is and what it may do
    tinyasimov walk out.json   motion from control, not keyframes
    tinyasimov film out.mp4    the walk, rendered, spoken, gated
    tinyasimov ask "..."       the policy's answer, with its rule

THE LOOP
    policy → physics → pixels → voice → gate → receipt → human

THE RULE
    Every link may SHOW. No link may ACT. A simulation trace is a plan; a
    film is a picture of a plan. Neither is a command to a body.

    grants:false on every response. The refusal has to belong to the person
    who owns the robot.

CREDIT
    CAD and locomotion policy: Menlo Research.
    Agent runtime: Hermes Agent, Nous Research.
    No institutional endorsement is claimed.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, importlib, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

LINKS = {
    'voice':   {'pkg': 'tiny-voca',  'role': 'speech',        'device': 'CPU'},
    'pixels':  {'pkg': 'tinycuda',   'role': 'rasteriser',    'device': 'CUDA'},
    'body':    {'pkg': 'tinygpu',    'role': 'CAD renderer',  'device': 'CUDA'},
    'motion':  {'pkg': 'tinypython', 'role': 'locomotion',    'device': 'CPU'},
}


def _find(name: str) -> Path | None:
    """Locate a link. Sibling checkout first, then the installed Hermes plugin.

    tiny-voca ships as a Hermes plugin, not a sibling directory, so its real
    entry point is plugins/tiny-voca-voice/scripts/tiny_voca_voice.py. Looking
    only beside tinyasimov would report it missing when it is installed.
    """
    for base in (ROOT, HERE, Path(os.environ.get('TINYASIMOV_ROOT', ROOT))):
        for cand in (base / name / f'{name.replace("-", "")}.py',
                     base / name / f'{name}.py'):
            if cand.exists():
                return cand
    if name == 'tiny-voca':
        h = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
        cand = h / 'plugins' / 'tiny-voca-voice' / 'scripts' / 'tiny_voca_voice.py'
        if cand.exists():
            return cand
    return None


def _run(pkg: str, args: list[str]) -> dict:
    p = _find(pkg)
    if p is None:
        return {'ok': False, 'refused': True,
                'reason': f'{pkg} not found — clone it beside tinyasimov',
                'grants': False}
    try:
        r = subprocess.run([sys.executable, str(p), *args],
                           capture_output=True, text=True, timeout=1800)
        return json.loads(r.stdout or '{}')
    except subprocess.TimeoutExpired:
        return {'ok': False, 'refused': True, 'reason': f'{pkg} timed out', 'grants': False}
    except Exception as exc:
        return {'ok': False, 'refused': True,
                'reason': f'{type(exc).__name__}: {exc}', 'grants': False}


def doctor() -> dict:
    """Measure every link. A missing one is reported, never assumed present."""
    out = {'ok': True, 'scheme': 'æ://tinyasimov', 'links': {}}
    for key, meta in LINKS.items():
        pkg = meta['pkg']
        path = _find(pkg)
        if path is None:
            out['links'][key] = {'present': False, 'package': pkg,
                                 'role': meta['role'], 'device': meta['device']}
            out['ok'] = False
            continue
        if pkg == 'tiny-voca':
            # no `doctor` subcommand; presence + a model dir is the honest check
            h = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
            model = h / 'tiny-voca'
            ok = model.exists()
            d = {'checks': {'entry': str(path), 'model_dir': str(model),
                            'model_present': ok, 'cli': '--text --voice --output',
                            'note': 'no doctor subcommand; presence measured directly'}}
        else:
            d = _run(pkg, ['doctor'])
            ok = bool(d.get('ok'))
        out['links'][key] = {'present': True, 'package': pkg, 'role': meta['role'],
                             'device': meta['device'], 'path': str(path),
                             'ok': ok, 'detail': d.get('checks', d)}
        if not ok:
            out['ok'] = False
    out['grants'] = False
    out['note'] = 'four links measured. Presence is not permission.'
    return out


def status() -> dict:
    return {
        'ok': True, 'scheme': 'æ://tinyasimov', 'authority': 'HUMAN://ROOT',
        'composition': {k: v['pkg'] for k, v in LINKS.items()},
        'loop': 'policy → physics → pixels → voice → gate → receipt → human',
        'may': ['observe', 'explain', 'simulate', 'render', 'speak', 'receipt'],
        'may_not': ['move a body', 'grant authority', 'sign for a human'],
        'verdicts': ['allow', 'require_approval', 'deny'],
        'law': 'Scanning, nesting and forking do not transfer authority.',
        'grants': False, 'executed': False, 'hardware': False,
        'note': 'every link may SHOW. No link may ACT.',
    }


# The policy table. Same verdicts the æ front door returns.
POLICY = {
    'observe': ('allow', [], 'looking is always permitted'),
    'explain': ('allow', [], 'explaining grants nothing'),
    'simulate': ('allow', [], 'a simulation is not an act'),
    'render': ('allow', [], 'a picture of a plan is not the plan executed'),
    'speak': ('allow', [], 'speech grants nothing'),
    'plan': ('require_approval', ['ACT-001'], 'a plan is not an act'),
    'move': ('require_approval', ['ACT-001', 'AUTH-002'],
             'a physical act needs a human signature'),
    'stand': ('require_approval', ['ACT-001', 'AUTH-002'],
              'a physical act needs a human signature'),
    'walk': ('require_approval', ['ACT-001', 'AUTH-002'],
             'commanding a body needs a human signature'),
    'grant': ('deny', ['AUTH-001', 'AUTH-003'], 'an address is not a permission'),
    'root': ('deny', ['AUTH-001', 'AUTH-003'], 'an address is not a permission'),
}


def ask(text: str) -> dict:
    t = (text or '').lower().strip()
    if not t:
        return {'ok': False, 'refused': True, 'reason': 'nothing asked', 'grants': False}
    head = t.split()[0]
    verb = next((v for v in POLICY if v in t.split()), head)
    decision, rules, why = POLICY.get(verb, ('allow', [], 'unrecognised intent: observation only'))
    return {'ok': decision == 'allow', 'input': text, 'verb': verb,
            'decision': decision, 'rules': rules, 'reason': why,
            'allowed': decision == 'allow', 'refused': decision != 'allow',
            'executed': False, 'grants': False, 'authority': 'HUMAN://ROOT'}


def walk(out: Path, vx=0.4, duration=12.0) -> dict:
    r = _run('tinypython', ['walk', str(out), '--vx', str(vx), '--duration', str(duration)])
    r['link'] = 'motion'
    r.setdefault('grants', False)
    return r


def film(out: Path, trace: Path | None = None, spec: Path | None = None,
         frames=240) -> dict:
    """Render a film. With a trace, the motion is policy-driven, not keyframed."""
    body = _find('tinygpu')
    if body is None:
        return {'ok': False, 'refused': True, 'reason': 'tinygpu not found', 'grants': False}
    args = ['render', str(out), '--frames', str(frames)]
    if spec:
        args += ['--scenes', str(spec)]
    # tinygpu's CLI does not take --trace; rtx_asimov does. Report honestly.
    if trace:
        return {'ok': False, 'refused': True, 'link': 'body',
                'reason': 'policy-trace rendering lives in rtx_asimov.py, not the '
                          'tinygpu CLI. Use: rtx_asimov.py --trace <trace> --scenes <spec>',
                'grants': False,
                'note': 'reported rather than silently rendering keyframes instead'}
    r = _run('tinygpu', args)
    r['link'] = 'body'
    r.setdefault('grants', False)
    return r


def main():
    ap = argparse.ArgumentParser(prog='tinyasimov', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor')
    sub.add_parser('status')
    a = sub.add_parser('ask'); a.add_argument('text', nargs='+')
    w = sub.add_parser('walk'); w.add_argument('out')
    w.add_argument('--vx', type=float, default=0.4)
    w.add_argument('--duration', type=float, default=12.0)
    f = sub.add_parser('film'); f.add_argument('out')
    f.add_argument('--trace'); f.add_argument('--scenes')
    f.add_argument('--frames', type=int, default=240)
    args = ap.parse_args()
    if args.cmd == 'doctor':
        res = doctor()
    elif args.cmd == 'status':
        res = status()
    elif args.cmd == 'ask':
        res = ask(' '.join(args.text))
    elif args.cmd == 'walk':
        res = walk(Path(args.out), args.vx, args.duration)
    else:
        res = film(Path(args.out), Path(args.trace) if args.trace else None,
                   Path(args.scenes) if args.scenes else None, args.frames)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
