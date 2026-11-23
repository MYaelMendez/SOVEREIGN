"""asimov:// — the OpenSourceWare command-and-control protocol for Asimov.

A governed address layer over the official Menlo SDK. It invents no wire
synonyms: every motion name is Menlo's own verb. It adds the two things the
SDK deliberately leaves to user code — an authority gate and a receipt — and
one transport the SDK does not ship: `sim`, so the same C2 path runs on a
laptop with no robot.

    asimov://                     protocol status + transports
    asimov://status               SDK version, robot presence, policy hash
    asimov://state                Robot.get_state()      (read, allow)
    asimov://verbs                the canonical verb set
    asimov://plan <verb>          policy-evaluated plan, never connects
    asimov://exec <verb>          dry-run unless HERMES_AE_SDK_LIVE=1
    asimov://sim <verb>           plan against the MuJoCo simulation transport
    asimov://grant <verb> <sha>   report the approval shape required (never self-grants)

Authority: HUMAN://ROOT. An address is not a permission. Fail closed.

Engines are wrapped, never reimplemented: ae_verbs.py owns the verb surface,
ae_policy.py owns the rules, daobrain.py owns deliberation.
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEME = 'asimov://'
AUTHORITY = 'HUMAN://ROOT'
HERMES_HOME = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
AE = Path(os.environ.get('HERMES_AE_HOME', HERMES_HOME / 'plugins' / 'hermes-ae'))
VERBS = AE / 'scripts' / 'ae_verbs.py'
PY = os.environ.get('HERMES_AE_PYTHON', sys.executable)
LEDGER = Path(os.environ.get('HERMES_ASIMOV_LEDGER', HERMES_HOME / 'asimov-protocol.jsonl'))

# The SDK ships three transports, all requiring hardware. `sim` is ours.
TRANSPORTS = {
    'udp':     {'official': True,  'requires': 'robot on a trusted LAN', 'media': False},
    'hybrid':  {'official': True,  'requires': 'robot + LiveKit',        'media': True},
    'livekit': {'official': True,  'requires': 'robot + room',           'media': True},
    'sim':     {'official': False, 'requires': 'a laptop (MuJoCo)',      'media': True,
                'note': 'OpenSourceWare addition; same verbs, same gates, same receipts'},
}
READ_VERBS = {'status', 'state', 'get_state', 'check'}


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _last_hash():
    if LEDGER.exists():
        lines = [l for l in LEDGER.read_text(encoding='utf-8').splitlines() if l.strip()]
        if lines:
            try:
                return json.loads(lines[-1])['hash']
            except Exception:
                pass
    return '0' * 64


def receipt(action, detail):
    body = {'ts': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'action': action, 'authority': AUTHORITY, 'detail': detail,
            'prev': _last_hash()}
    body['hash'] = hashlib.sha256(_canonical(body).encode('utf-8')).hexdigest()
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open('a', encoding='utf-8') as fh:
        fh.write(_canonical(body) + '\n')
    return body


def _engine(args):
    """Call the existing verb engine. Never reimplement its rules."""
    if not VERBS.exists():
        return {'success': False, 'refused': True,
                'reason': f'verb engine missing: {VERBS}'}
    env = dict(os.environ)
    env.setdefault('HERMES_AE_PYTHON', PY)
    p = subprocess.run([PY, str(VERBS), _canonical(args)],
                       capture_output=True, text=True, encoding='utf-8',
                       timeout=180, env=env)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {'success': False, 'refused': True,
                'reason': (p.stderr or p.stdout or 'no output')[-400:]}


def parse(raw):
    """asimov://<route> [args...]  ->  (route, args). Longest-prefix friendly."""
    s = raw.strip()
    if s.startswith(SCHEME):
        s = s[len(SCHEME):]
    parts = s.split()
    if not parts:
        return '', []
    return parts[0].lower(), parts[1:]


def _sdk_facts():
    try:
        import importlib.metadata as md
        ver = md.version('menlo-sdk')
    except Exception:
        ver = None
    return {'menlo_sdk': ver or 'not installed',
            'robot_configured': bool(os.environ.get('MENLO_ROBOT') or os.environ.get('MENLO_UDP_HOST')),
            'live': os.environ.get('HERMES_AE_SDK_LIVE') == '1'}


def status():
    facts = _sdk_facts()
    pol = _engine({'action': 'list'})
    return {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'protocol': 'asimov-protocol/1',
            'sdk': facts, 'transports': TRANSPORTS,
            'verb_count': pol.get('count'),
            'chain': 'HUMAN://ROOT → æ POLICY → asimov:// → menlo.asimov.Robot → RECEIPT',
            'rule': 'An address is not a permission. Motion needs approval or an armed deadman.'}


def verbs():
    r = _engine({'action': 'list'})
    r.update(scheme=SCHEME, authority=AUTHORITY)
    return r


def plan(verb, transport='auto', extra=None):
    if not verb:
        return {'success': False, 'refused': True, 'reason': 'verb required',
                'available': sorted(READ_VERBS) + ['stand', 'damp', 'balance', 'set_velocity',
                                                   'trajectory', 'set_joints', 'photo',
                                                   'capture_clip', 'record_audio', 'play_pcm']}
    args = {'action': 'plan', 'verb': verb}
    if extra:
        args.update(extra)
    r = _engine(args)
    cls = 'read' if verb in READ_VERBS else ('media' if verb in
           ('photo', 'capture_clip', 'record_audio', 'play_pcm') else 'motion')
    out = {'success': bool(r.get('success')), 'scheme': SCHEME, 'authority': AUTHORITY,
           'address': f'{SCHEME}plan {verb}', 'verb': verb, 'class': cls,
           'transport': transport, 'decision': r.get('decision'),
           'allowed': r.get('allowed', False), 'rules': r.get('rules', []),
           'official': r.get('official'), 'plan': r.get('plan'),
           'args_sha256': r.get('args_sha256'), 'executed': False}
    if r.get('refused') or not r.get('success'):
        out['refused'] = True
        out['reason'] = r.get('reason') or r.get('error')
    out['receipt'] = receipt('ASIMOV://PLAN', {k: out[k] for k in
                             ('verb', 'class', 'transport', 'decision', 'allowed', 'rules')})
    return out


def execute(verb, extra=None):
    if not verb:
        return {'success': False, 'refused': True, 'reason': 'verb required'}
    args = {'action': 'execute', 'verb': verb}
    if extra:
        args.update(extra)
    r = _engine(args)
    out = dict(r)
    out.update(scheme=SCHEME, authority=AUTHORITY, address=f'{SCHEME}exec {verb}')
    out['receipt'] = receipt('ASIMOV://EXEC', {'verb': verb,
                             'decision': r.get('decision'), 'executed': r.get('executed', False),
                             'mode': r.get('mode')})
    return out


def sim(verb):
    """Drive the TWIN, never hardware.

    `executed` reports the rollout truthfully; `hardware:false` and `grants:false`
    are invariant. This is a different fact from `exec` (real body, bound grant).
    No actuated Asimov model exists on this host (nu=0), so the rollout is on the
    published open-loop plant and is labelled as such.
    """
    out = plan(verb, transport='sim')
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'ae_tinymujoco_instrument', 'C:/æ/tinymujoco/tinymujoco.py')
        inst = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inst)
        roll = inst.rollout(
            Path('C:/Users/yaelm/AppData/Local/hermes/cache/scratch/asimov-twin/1.0.0/model/asimov_1_25dof.xml'),
            seed=0, steps=60)
        executed = bool(roll.get('ok'))
        trace = roll.get('trace_sha256', '')
        nu = roll.get('nu', 0)
    except Exception as exc:
        executed, trace, nu = False, '', None
        roll = {'reason': f'{type(exc).__name__}: {exc}'}
    out['sim'] = {'engine': 'MuJoCo',
                  'model': 'asimov_1_25dof.xml (published twin, open-loop)',
                  'status': 'twin rollout' if executed else 'twin rollout unavailable',
                  'requires': 'no robot',
                  'trace_sha256': trace, 'nu': nu,
                  'detail': roll.get('reason')}
    out.update({'executed': executed, 'hardware': False, 'grants': False,
                'granted': False, 'address': f'{SCHEME}sim {verb}',
                'note': 'executed on the TWIN; no hardware contact, no authority granted'})
    out['receipt'] = receipt('ASIMOV://SIM', {'verb': verb, 'executed': executed,
                                             'hardware': False, 'trace_sha256': trace})
    return out


def grant(verb):
    """Report the approval shape. This NEVER grants anything."""
    if not verb:
        return {'success': False, 'refused': True, 'reason': 'verb required'}
    sha = hashlib.sha256(_canonical({}).encode('utf-8')).hexdigest()
    return {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'verb': verb, 'grants': False,
            'note': 'This reports the required shape. It does not authorize. Only the human signs.',
            'required': {'approval': {'human': True, 'action_sha256': sha,
                                      'expires_at': '<ISO-8601, must be future>'},
                         'or_controls': {'arm': True, 'deadman': True}}}


def dispatch(raw):
    route, args = parse(raw)
    if route in ('', 'status'):
        return status()
    if route == 'verbs':
        return verbs()
    if route == 'state':
        return execute('state')
    if route == 'plan':
        return plan(args[0] if args else None,
                    transport=args[1] if len(args) > 1 else 'auto')
    if route in ('exec', 'execute', 'call'):
        return execute(args[0] if args else None)
    if route == 'sim':
        return sim(args[0] if args else None)
    if route == 'grant':
        return grant(args[0] if args else None)
    # fail closed — an unknown route is a refusal, never a silent fallthrough
    return {'success': False, 'refused': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'address': raw, 'reason': f'unknown route {route!r}',
            'routes': ['', 'status', 'state', 'verbs', 'plan', 'exec', 'sim', 'grant']}


def main():
    raw = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else SCHEME
    print(json.dumps(dispatch(raw), ensure_ascii=False))


if __name__ == '__main__':
    main()
