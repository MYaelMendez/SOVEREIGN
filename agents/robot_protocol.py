"""robot:// — one governed address space for every robot stack.

Not a new protocol. A dispatcher: each robot keeps its own dialect (its own
verbs, its own gate, its own receipt ledger) and `robot://` is the single front
door that routes to it. Longest-prefix, like every other æ:// scheme.

    robot://                       fleet status — which robots are present
    robot://robots                 the registry, with each robot's transports
    robot://fleet/ledger           the three dialect ledgers, hashed together
    robot://<robot>/<route> [args] delegated to that robot's dialect

    robot://reachy/verbs
    robot://reachy/plan goto_target
    robot://reachy/sim  goto_target   (official mockup-sim daemon)
    robot://microduck/status
    robot://microduck/sim robot.move  (official duck-sim twin)
    robot://asimov/plan stand         (Menlo SDK; sim = MuJoCo)

Authority: HUMAN://ROOT. An address is not a permission. Fail closed.
Every dialect writes its own ledger; robot:// adds the fleet receipt on
cross-robot routes, so a fleet action is itself recorded.
"""
import hashlib
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEME = 'robot://'
AUTHORITY = 'HUMAN://ROOT'
HERE = Path(__file__).resolve().parent
HERMES_HOME = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
LEDGER = Path(os.environ.get('HERMES_ROBOT_LEDGER', HERMES_HOME / 'robot-protocol.jsonl'))

# The registry. Each entry names the dialect module and its human surface.
# A robot is only "present" if its dialect module imports and reports success.
ROBOTS = {
    'asimov': {
        'module': 'asimov_protocol', 'scheme': 'asimov://',
        'sdk': 'menlo-sdk (Menlo)', 'robot': 'Asimov humanoid',
        'sim': 'MuJoCo (æ addition, plan only)',
    },
    'reachy': {
        'module': 'reachy_protocol', 'scheme': 'reachy://',
        'sdk': 'reachy_mini 1.12.0.dev0', 'robot': 'Reachy Mini',
        'sim': 'MockupSimBackend (official, use_sim=True)',
    },
    'microduck': {
        'module': 'microduck_protocol', 'scheme': 'microduck://',
        'sdk': 'duckctl / robotctl (Pollen)', 'robot': 'Microduck',
        'sim': 'duck-sim + duck-body (official twin)',
    },
}

# Cross-robot routes that robot:// answers itself.
FLEET_ROUTES = {'', 'robots', 'fleet', 'fleet/ledger', 'status'}


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


def _load(name):
    """Import a dialect once. A missing dialect is a refusal, never a crash."""
    if name in sys.modules:
        return sys.modules[name]
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    return importlib.import_module(name)


def _robot_status(name, meta):
    try:
        mod = _load(meta['module'])
        st = mod.status()
        return {'robot': name, 'scheme': meta['scheme'], 'module': meta['module'],
                'sdk': meta['sdk'], 'sim': meta['sim'],
                'present': bool(st.get('success')),
                'verb_count': st.get('verb_count'),
                'transports': list((st.get('transports') or {}).keys()),
                'live': (st.get('sdk') or {}).get('live', False)}
    except Exception as exc:
        return {'robot': name, 'scheme': meta['scheme'], 'module': meta['module'],
                'sdk': meta['sdk'], 'sim': meta['sim'], 'present': False,
                'reason': f'{type(exc).__name__}: {exc}'}


def fleet():
    robots = {name: _robot_status(name, meta) for name, meta in ROBOTS.items()}
    return {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'protocol': 'robot-protocol/1',
            'robots': robots, 'present': [n for n, r in robots.items() if r['present']],
            'count': len(robots),
            'chain': 'HUMAN://ROOT → æ POLICY → robot:// → {asimov|reachy|microduck}:// → RECEIPT',
            'rule': 'An address is not a permission. Motion needs approval or an armed deadman.'}


def fleet_ledger():
    """Hash each dialect's ledger tail together, so the fleet receipt is anchored."""
    per = {}
    for name, meta in ROBOTS.items():
        path = HERMES_HOME / f"{name}-protocol.jsonl"
        if not path.exists():
            per[name] = {'ledger': str(path), 'receipts': 0, 'tail': None}
            continue
        lines = [l for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]
        tail = json.loads(lines[-1])['hash'] if lines else None
        per[name] = {'ledger': str(path), 'receipts': len(lines), 'tail': tail}
    # the fleet's own ledger is part of the anchor, so a fleet action is recorded too
    fleet_path = Path(LEDGER)
    if fleet_path.exists():
        flines = [l for l in fleet_path.read_text(encoding='utf-8').splitlines() if l.strip()]
        per['robot'] = {'ledger': str(fleet_path), 'receipts': len(flines),
                        'tail': json.loads(flines[-1])['hash'] if flines else None}
    else:
        per['robot'] = {'ledger': str(fleet_path), 'receipts': 0, 'tail': None}
    combined = hashlib.sha256(_canonical(per).encode('utf-8')).hexdigest()
    return {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'ledgers': per, 'combined_sha256': combined}


def parse(raw):
    """robot://<robot>/<route...> — the robot is the first path segment."""
    s = raw.strip()
    if s.startswith(SCHEME):
        s = s[len(SCHEME):]
    parts = s.split()
    head = parts[0] if parts else ''
    args = parts[1:]
    if '/' in head:
        name, rest = head.split('/', 1)
        return name.lower(), ([rest] if rest else []) + args
    return head.lower(), args


def _record(raw, robot, out):
    """Every dispatch leaves a fleet receipt, and the hash rides on the result.

    The docstring's promise made real: robot:// records the fleet action, so a
    route through the dispatcher is itself anchored in the hash chain.
    """
    out = dict(out)
    rec = receipt('dispatch', {'address': raw, 'robot': robot,
                               'success': bool(out.get('success')),
                               'refused': bool(out.get('refused'))})
    out['fleet_receipt'] = rec['hash']
    return out


def dispatch(raw):
    route, args = parse(raw)
    if route == 'fleet' and args == ['ledger']:
        # not recorded: the combined hash would otherwise be self-referential
        return fleet_ledger()
    if route in FLEET_ROUTES:
        return _record(raw, None, fleet())
    name = route
    if name not in ROBOTS:
        return _record(raw, None, {'success': False, 'refused': True, 'scheme': SCHEME,
                                   'authority': AUTHORITY, 'address': raw,
                                   'reason': f'unknown robot {name!r}',
                                   'robots': sorted(ROBOTS)})
    meta = ROBOTS[name]
    sub_route = ' '.join(args)
    try:
        mod = _load(meta['module'])
    except Exception as exc:
        return _record(raw, name, {'success': False, 'refused': True, 'scheme': SCHEME,
                                   'authority': AUTHORITY, 'robot': name,
                                   'reason': f'dialect {meta["module"]} did not import: {exc}'})
    out = mod.dispatch(sub_route) if sub_route else mod.status()
    out = dict(out)
    out['scheme'] = meta['scheme']
    out['robot'] = name
    out['via'] = SCHEME
    out['address'] = f'{SCHEME}{name}/{sub_route}'.rstrip('/')
    return _record(raw, name, out)


def main():
    raw = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else SCHEME
    print(json.dumps(dispatch(raw), ensure_ascii=False))


if __name__ == '__main__':
    main()
