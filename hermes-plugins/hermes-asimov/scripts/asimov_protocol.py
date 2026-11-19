"""asimov:// — the OpenSourceWare command-and-control protocol for Asimov.

A governed address layer over the official Menlo SDK. It invents no wire
synonyms: every motion name is Menlo's own verb. It adds the two things the
SDK leaves to user code — an authority gate and a receipt — and one transport
the SDK does not ship: `sim`, which returns a policy-evaluated plan bound to
the simulation transport and does not connect.

    asimov://                     protocol status + transports
    asimov://status               SDK version, robot presence, policy hash
    asimov://state                Robot.get_state()      (read, allow)
    asimov://verbs                the canonical verb set + composites
    asimov://plan <verb>          policy-evaluated plan, never connects
    asimov://exec <verb>          dry-run unless HERMES_AE_SDK_LIVE=1
    asimov://sim <verb>           plan against the MuJoCo simulation transport
    asimov://grant <verb> <sha>   report the approval shape required (never self-grants)

`walk` is a composite, matching the Menlo CLI's "walk for a bounded time, then
balance in place". It is not a wire verb: it expands to Robot.set_velocity(...)
for duration_s seconds, then Robot.balance(). It is class 'motion' and passes
the same policy gate as stand (require_approval / ACT-001). Duration comes from
--duration N or a JSON argument ({"duration_s": N}); it defaults to 2.0 s and
is clamped to WALK_MAX_S.

Outcomes are tri-state: 'applied' (a verdict arrived and the command took
effect), 'refused' (policy or the protocol denied the request), 'unknown'
(the command was sent but no verdict arrived). 'unknown' is never success and
never refusal. A plan never connects, so its outcome is 'refused' when policy
denied it and 'unknown' otherwise: nothing was sent, so nothing is known about
the effect. See classify().

Authority: HUMAN://ROOT. An address is not a permission. Fail closed.

Engines are wrapped, never reimplemented: ae_verbs.py owns the verb surface,
ae_policy.py owns the rules, daobrain.py owns deliberation.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEME = 'asimov://'
AUTHORITY = 'HUMAN://ROOT'
HERMES_HOME = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
AE = Path(os.environ.get('HERMES_AE_HOME', HERMES_HOME / 'plugins' / 'hermes-ae'))
VERBS = AE / 'scripts' / 'ae_verbs.py'
PY = os.environ.get('HERMES_AE_PYTHON', sys.executable)
LEDGER = Path(os.environ.get('HERMES_ASIMOV_LEDGER', HERMES_HOME / 'asimov-protocol.jsonl'))

# The SDK ships three transports, all requiring hardware. `sim` is ours.
TRANSPORTS: dict[str, dict[str, Any]] = {
    'udp':     {'official': True,  'requires': 'robot on a trusted LAN', 'media': False},
    'hybrid':  {'official': True,  'requires': 'robot + LiveKit',        'media': True},
    'livekit': {'official': True,  'requires': 'robot + room',           'media': True},
    'sim':     {'official': False, 'requires': 'a laptop (MuJoCo)',      'media': True,
                'note': 'OpenSourceWare addition; same verbs, same gates, same receipts'},
}
READ_VERBS: set[str] = {'status', 'state', 'get_state', 'check'}
MEDIA_VERBS: set[str] = {'photo', 'capture_clip', 'record_audio', 'play_pcm'}
MOTION_VERBS: set[str] = {'stand', 'damp', 'balance', 'set_velocity', 'trajectory', 'set_joints'}

# walk: the Menlo CLI composite. Bounded velocity, then balance in place.
WALK_DEFAULT_S: float = 2.0
WALK_MAX_S: float = 10.0
OUTCOMES: tuple[str, str, str] = ('applied', 'refused', 'unknown')


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _last_hash() -> str:
    if LEDGER.exists():
        lines = [l for l in LEDGER.read_text(encoding='utf-8').splitlines() if l.strip()]
        if lines:
            try:
                return json.loads(lines[-1])['hash']
            except Exception:
                pass
    return '0' * 64


def receipt(action: str, detail: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        'ts': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'action': action, 'authority': AUTHORITY, 'detail': detail,
        'prev': _last_hash()}
    body['hash'] = hashlib.sha256(_canonical(body).encode('utf-8')).hexdigest()
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open('a', encoding='utf-8') as fh:
        fh.write(_canonical(body) + '\n')
    return body


def classify(result: dict[str, Any]) -> str:
    """Tri-state verdict for a command result.

    'refused'  — the protocol or policy denied the request (explicit refusal
                 flag, or a policy 'deny' decision).
    'applied'  — the engine executed the command and returned a successful
                 verdict.
    'unknown'  — everything else: the command was sent but no verdict arrived,
                 or nothing was sent and nothing is known about the effect
                 (dry-run plans, missing verdicts, transport errors).

    'unknown' is never mapped to success and never mapped to refusal.
    """
    if result.get('refused') or result.get('decision') == 'deny':
        return 'refused'
    if result.get('executed') and result.get('success'):
        return 'applied'
    return 'unknown'


def _normalize(r: dict[str, Any]) -> dict[str, Any]:
    """Fail closed: an engine response that never reached policy evaluation
    (no decision) and did not succeed is a refusal, not an unknown."""
    out = dict(r)
    if not out.get('success') and out.get('decision') is None and not out.get('refused'):
        out['refused'] = True
        out.setdefault('reason', out.get('error') or out.get('reason'))
    return out


def _engine(args: dict[str, Any]) -> dict[str, Any]:
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


def parse(raw: str) -> tuple[str, list[str]]:
    """asimov://<route> [args...]  ->  (route, args). Longest-prefix friendly."""
    s = raw.strip()
    if s.startswith(SCHEME):
        s = s[len(SCHEME):]
    parts = s.split()
    if not parts:
        return '', []
    return parts[0].lower(), parts[1:]


def _extra_from_tokens(tokens: list[str]) -> dict[str, Any]:
    """Parse trailing route arguments: a JSON object and/or --duration N
    (also --duration=N). Raises ValueError on malformed input."""
    extra: dict[str, Any] = {}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.startswith('{'):
            # parse() splits on whitespace, so a JSON object may span several
            # tokens; reassemble until it parses (fail closed if it never does)
            buf = t
            j = i
            while True:
                try:
                    obj = json.loads(buf)
                    break
                except ValueError:
                    j += 1
                    if j >= len(tokens):
                        raise ValueError(f'malformed JSON argument: {buf}')
                    buf += ' ' + tokens[j]
            if not isinstance(obj, dict):
                raise ValueError('JSON argument must be an object')
            extra.update(obj)
            i = j
        elif t == '--duration' and i + 1 < len(tokens):
            extra['duration_s'] = float(tokens[i + 1])
            i += 1
        elif t.startswith('--duration='):
            extra['duration_s'] = float(t.split('=', 1)[1])
        i += 1
    return extra


def _walk_duration(extra: dict[str, Any] | None) -> tuple[float, bool]:
    """Resolve the walk duration: JSON 'duration_s'/'duration' or the default.
    Returns (seconds, clamped). Negative values floor at 0; values above
    WALK_MAX_S clamp to WALK_MAX_S. Raises ValueError on non-numeric input."""
    raw: Any = WALK_DEFAULT_S
    if extra:
        raw = extra.get('duration_s', extra.get('duration', WALK_DEFAULT_S))
    d = float(raw)
    if d < 0.0:
        d = 0.0
    clamped = d > WALK_MAX_S
    return min(d, WALK_MAX_S), clamped


def _walk_steps(duration_s: float) -> list[dict[str, Any]]:
    """The composite expansion of the Menlo CLI walk verb."""
    return [{'official': 'Robot.set_velocity(...)', 'duration_s': duration_s},
            {'official': 'Robot.balance()'}]


def _sdk_facts() -> dict[str, Any]:
    try:
        import importlib.metadata as md
        ver = md.version('menlo-sdk')
    except Exception:
        ver = None
    return {'menlo_sdk': ver or 'not installed',
            'robot_configured': bool(os.environ.get('MENLO_ROBOT') or os.environ.get('MENLO_UDP_HOST')),
            'live': os.environ.get('HERMES_AE_SDK_LIVE') == '1'}


def status() -> dict[str, Any]:
    facts = _sdk_facts()
    pol = _engine({'action': 'list'})
    return {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'protocol': 'asimov-protocol/1',
            'sdk': facts, 'transports': TRANSPORTS,
            'verb_count': pol.get('count'),
            'composites': ['walk'], 'outcomes': list(OUTCOMES),
            'chain': 'HUMAN://ROOT → æ POLICY → asimov:// → menlo.asimov.Robot → RECEIPT',
            'rule': 'An address is not a permission. Motion needs approval or an armed deadman.'}


def verbs() -> dict[str, Any]:
    r = _engine({'action': 'list'})
    r.update(scheme=SCHEME, authority=AUTHORITY)
    r['composites'] = {
        'walk': {'composite': True, 'class': 'motion',
                 'steps': ['Robot.set_velocity(...)', 'Robot.balance()'],
                 'gate': 'same policy gate as stand (require_approval / ACT-001)',
                 'default_duration_s': WALK_DEFAULT_S, 'max_duration_s': WALK_MAX_S,
                 'note': 'Menlo CLI walk: walk for a bounded time, then balance in '
                         'place. A composite of wire verbs, not a wire verb itself.'}}
    return r


def _plan_walk(transport: str, extra: dict[str, Any] | None) -> dict[str, Any]:
    """Policy-evaluated plan for the walk composite. Gates exactly like stand:
    the decision, rules and allowed flag come from the engine's stand plan."""
    address = f'{SCHEME}plan walk'
    try:
        duration, clamped = _walk_duration(extra)
    except (TypeError, ValueError):
        return {'success': False, 'refused': True, 'outcome': 'refused',
                'scheme': SCHEME, 'authority': AUTHORITY, 'address': address,
                'verb': 'walk', 'reason': 'duration must be a number'}
    gate = _engine({'action': 'plan', 'verb': 'stand'})
    steps = _walk_steps(duration)
    out: dict[str, Any] = {
        'success': bool(gate.get('success')), 'scheme': SCHEME, 'authority': AUTHORITY,
        'address': address, 'verb': 'walk', 'composite': True, 'class': 'motion',
        'transport': transport, 'decision': gate.get('decision'),
        'allowed': gate.get('allowed', False), 'rules': gate.get('rules', []),
        'official': 'composite of Menlo wire verbs: Robot.set_velocity(...) then Robot.balance()',
        'steps': steps, 'duration_s': duration,
        'plan': {'composite': True, 'steps': steps},
        'gate': 'same policy gate as stand (motion / ACT-001)',
        'executed': False}
    if clamped:
        out['duration_clamped_to_max_s'] = WALK_MAX_S
    if gate.get('refused') or not gate.get('success'):
        out['refused'] = True
        out['reason'] = gate.get('reason') or gate.get('error')
    out['outcome'] = classify(out)
    detail = {k: out[k] for k in ('verb', 'class', 'transport', 'decision', 'allowed', 'rules', 'outcome')}
    detail.update(composite=True, duration_s=duration)
    out['receipt'] = receipt('ASIMOV://PLAN', detail)
    return out


def plan(verb: str | None, transport: str = 'auto',
         extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Policy-evaluated plan. Never connects. Outcome is 'refused' when policy
    denied the request, else 'unknown': nothing was sent, so nothing is known
    about the effect."""
    if not verb:
        return {'success': False, 'refused': True, 'outcome': 'refused',
                'reason': 'verb required',
                'available': sorted(READ_VERBS | MOTION_VERBS | MEDIA_VERBS) + ['walk']}
    if verb == 'walk':
        return _plan_walk(transport, extra)
    args: dict[str, Any] = {'action': 'plan', 'verb': verb}
    if extra:
        args.update(extra)
    r = _engine(args)
    cls = 'read' if verb in READ_VERBS else ('media' if verb in MEDIA_VERBS else 'motion')
    out: dict[str, Any] = {
        'success': bool(r.get('success')), 'scheme': SCHEME, 'authority': AUTHORITY,
        'address': f'{SCHEME}plan {verb}', 'verb': verb, 'class': cls,
        'transport': transport, 'decision': r.get('decision'),
        'allowed': r.get('allowed', False), 'rules': r.get('rules', []),
        'official': r.get('official'), 'plan': r.get('plan'),
        'args_sha256': r.get('args_sha256'), 'executed': False}
    if r.get('refused') or not r.get('success'):
        out['refused'] = True
        out['reason'] = r.get('reason') or r.get('error')
    out['outcome'] = classify(out)
    out['receipt'] = receipt('ASIMOV://PLAN', {k: out[k] for k in
                             ('verb', 'class', 'transport', 'decision', 'allowed', 'rules', 'outcome')})
    return out


def _exec_walk(extra: dict[str, Any] | None) -> dict[str, Any]:
    """Execute walk as its gated steps: set_velocity, hold for duration_s when
    the first step actually executed, then balance. Each step passes the same
    engine gate as any motion verb. The composite outcome is 'refused' if any
    step was refused, 'applied' only if every step returned a successful
    verdict, else 'unknown'."""
    address = f'{SCHEME}exec walk'
    try:
        duration, clamped = _walk_duration(extra)
    except (TypeError, ValueError):
        return {'success': False, 'refused': True, 'outcome': 'refused',
                'scheme': SCHEME, 'authority': AUTHORITY, 'address': address,
                'verb': 'walk', 'reason': 'duration must be a number'}
    passthrough = {k: v for k, v in (extra or {}).items()
                   if k in ('vx', 'vy', 'vyaw', 'approval', 'controls', 'actor', 'source', 'live')}
    r1 = _normalize(_engine({'action': 'execute', 'verb': 'set_velocity', **passthrough}))
    o1 = classify(r1)
    steps: list[dict[str, Any]] = [
        {'verb': 'set_velocity', 'official': 'Robot.set_velocity(...)', 'duration_s': duration,
         'decision': r1.get('decision'), 'executed': r1.get('executed', False), 'outcome': o1}]
    results = [r1]
    if o1 != 'refused':
        if r1.get('executed'):
            time.sleep(duration)
        balance_args = {k: v for k, v in passthrough.items()
                        if k in ('approval', 'controls', 'actor', 'source', 'live')}
        r2 = _normalize(_engine({'action': 'execute', 'verb': 'balance', **balance_args}))
        o2 = classify(r2)
        steps.append({'verb': 'balance', 'official': 'Robot.balance()',
                      'decision': r2.get('decision'), 'executed': r2.get('executed', False), 'outcome': o2})
        results.append(r2)
    outcomes = [s['outcome'] for s in steps]
    if 'refused' in outcomes:
        outcome = 'refused'
    elif len(steps) == 2 and all(o == 'applied' for o in outcomes):
        outcome = 'applied'
    else:
        outcome = 'unknown'
    out: dict[str, Any] = {
        'success': outcome != 'refused' and all(bool(r.get('success')) for r in results),
        'scheme': SCHEME, 'authority': AUTHORITY, 'address': address,
        'verb': 'walk', 'composite': True, 'class': 'motion',
        'steps': steps, 'duration_s': duration,
        'executed': len(steps) == 2 and all(bool(r.get('executed')) for r in results),
        'mode': results[0].get('mode'), 'outcome': outcome}
    if clamped:
        out['duration_clamped_to_max_s'] = WALK_MAX_S
    if outcome == 'refused':
        out['refused'] = True
        out['reason'] = next((r.get('reason') or r.get('error') for r in results
                              if r.get('refused') or r.get('decision') == 'deny'), None)
    out['receipt'] = receipt('ASIMOV://EXEC', {'verb': 'walk', 'composite': True,
                             'duration_s': duration, 'executed': out['executed'],
                             'mode': out['mode'], 'outcome': outcome})
    return out


def execute(verb: str | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a verb through the engine. Dry-run unless HERMES_AE_SDK_LIVE=1.
    Every response carries a tri-state outcome (see classify)."""
    if not verb:
        return {'success': False, 'refused': True, 'outcome': 'refused', 'reason': 'verb required'}
    if verb == 'walk':
        return _exec_walk(extra)
    args: dict[str, Any] = {'action': 'execute', 'verb': verb}
    if extra:
        args.update(extra)
    r = _normalize(_engine(args))
    out = dict(r)
    out.update(scheme=SCHEME, authority=AUTHORITY, address=f'{SCHEME}exec {verb}')
    out['outcome'] = classify(out)
    out['receipt'] = receipt('ASIMOV://EXEC', {'verb': verb,
                             'decision': r.get('decision'), 'executed': r.get('executed', False),
                             'mode': r.get('mode'), 'outcome': out['outcome']})
    return out


def sim(verb: str | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a policy-evaluated plan bound to the simulation transport.
    It does not connect; no hardware is touched."""
    out = plan(verb, transport='sim', extra=extra)
    out['sim'] = {'engine': 'MuJoCo', 'model': 'asimov_1_25dof_actuated.xml',
                  'status': 'policy-evaluated plan bound to the simulation transport; does not connect',
                  'requires': 'no robot'}
    out['address'] = f'{SCHEME}sim {verb}' if verb else f'{SCHEME}sim'
    return out


def grant(verb: str | None) -> dict[str, Any]:
    """Report the approval shape. This NEVER grants anything."""
    if not verb:
        return {'success': False, 'refused': True, 'outcome': 'refused', 'reason': 'verb required'}
    sha = hashlib.sha256(_canonical({}).encode('utf-8')).hexdigest()
    return {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'verb': verb, 'grants': False,
            'note': 'This reports the required shape. It does not authorize. Only the human signs.',
            'required': {'approval': {'human': True, 'action_sha256': sha,
                                      'expires_at': '<ISO-8601, must be future>'},
                         'or_controls': {'arm': True, 'deadman': True}}}


def dispatch(raw: str) -> dict[str, Any]:
    route, args = parse(raw)
    if route in ('', 'status'):
        return status()
    if route == 'verbs':
        return verbs()
    if route == 'state':
        return execute('state')
    if route in ('plan', 'exec', 'execute', 'call', 'sim'):
        verb = args[0] if args else None
        try:
            extra = _extra_from_tokens(args[1:])
        except ValueError as exc:
            return {'success': False, 'refused': True, 'outcome': 'refused',
                    'scheme': SCHEME, 'authority': AUTHORITY, 'address': raw,
                    'reason': f'bad arguments: {exc}'}
        if route == 'plan':
            return plan(verb, extra=extra)
        if route == 'sim':
            return sim(verb, extra=extra)
        return execute(verb, extra=extra)
    if route == 'grant':
        return grant(args[0] if args else None)
    # fail closed — an unknown route is a refusal, never a silent fallthrough
    return {'success': False, 'refused': True, 'outcome': 'refused',
            'scheme': SCHEME, 'authority': AUTHORITY,
            'address': raw, 'reason': f'unknown route {route!r}',
            'routes': ['', 'status', 'state', 'verbs', 'plan', 'exec', 'sim', 'grant']}


def main() -> None:
    raw = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else SCHEME
    print(json.dumps(dispatch(raw), ensure_ascii=False))


if __name__ == '__main__':
    main()
