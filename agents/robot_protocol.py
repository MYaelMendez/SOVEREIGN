"""robot:// — one governed address space for every robot stack.

Not a new protocol. A dispatcher: each robot keeps its own dialect (its own
verbs, its own gate, its own receipt ledger) and `robot://` is the single front
door that routes to it. Longest-prefix, like every other æ:// scheme.

    robot://                       fleet status — which robots are present
    robot://robots                 the registry, with each robot's transports
    robot://doctor                 probe every robot AND every dialect on disk
    robot://fleet/authority        per-robot gate classes + the grant shape
    robot://fleet/ledger           the dialect ledgers, hashed together
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
    # Mesh bodies: rigs on disk, no vendor SDK, no physics, no actuators.
    # `meshbot://` gives them the same seven standard routes; the verdict is a
    # named refusal rather than a crash. See agents/meshbot_protocol.py.
    'Soldier': {
        'module': 'meshbot_protocol', 'scheme': 'meshbot://',
        'sdk': 'mesh (Soldier.glb)', 'robot': 'Soldier', 'body': 'Soldier',
        'sim': 'none — no physics model',
    },
    'Xbot': {
        'module': 'meshbot_protocol', 'scheme': 'meshbot://',
        'sdk': 'mesh (Xbot.glb)', 'robot': 'Xbot', 'body': 'Xbot',
        'sim': 'none — no physics model',
    },
    'kira': {
        'module': 'meshbot_protocol', 'scheme': 'meshbot://',
        'sdk': 'mesh (kira.glb)', 'robot': 'kira', 'body': 'kira',
        'sim': 'none — no physics model',
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
        fn = getattr(mod, 'status_for', None)
        st = fn(meta.get('body') or name) if fn else mod.status()
        sdk = st.get('sdk')
        return {'robot': name, 'scheme': meta['scheme'], 'module': meta['module'],
                'sdk': meta['sdk'], 'sim': meta['sim'],
                'present': bool(st.get('success')),
                'verb_count': st.get('verb_count'),
                'transports': list((st.get('transports') or {}).keys()),
                'live': (sdk.get('live', False) if isinstance(sdk, dict) else False)}
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
        path = _dialect_ledger(meta, name) or (HERMES_HOME / f"{name}-protocol.jsonl")
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


def fleet_anchor():
    """The published ledger anchor: one tail per rostered body, hashed together.

    Derived from `fleet_ledger()`, but the fleet's own `robot-protocol.jsonl` is
    excluded on purpose: it records every dispatch — including the act of
    measuring — so its tail moves while the artifact is being read, and an
    anchor that changes under you is not an anchor. What is anchored is each
    dialect's chain, which is the evidence the page shows (six tails).
    """
    led = fleet_ledger()['ledgers']
    per_robot = {n: led[n] for n in ROBOTS if n in led}
    combined = hashlib.sha256(_canonical(per_robot).encode('utf-8')).hexdigest()
    return {'per_robot': per_robot, 'combined_sha256': combined}


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


# --------------------------------------------------------------------------
# the house style: every instrument has a doctor
# --------------------------------------------------------------------------

def _ledger_tail(name, meta=None):
    """The dialect's own ledger, read back — a chain is a fact, not a claim.

    The path is the dialect's REAL ledger: a dialect serving several bodies may
    declare one shared file (meshbot does), and the convention otherwise is
    HERMES_HOME/<dialect>-protocol.jsonl. Reading it by robot name alone is how
    the three mesh bodies came to report an empty ledger they do not have.
    """
    path = resolve_ledger(meta or ROBOTS.get(name, {}), name)
    if not path.exists():
        return {'ledger': str(path), 'receipts': 0, 'tail': None}
    lines = [l for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]
    if not lines:
        return {'ledger': str(path), 'receipts': 0, 'tail': None}
    try:
        return {'ledger': str(path), 'receipts': len(lines),
                'tail': json.loads(lines[-1])['hash']}
    except Exception as exc:
        return {'ledger': str(path), 'receipts': len(lines), 'tail': None,
                'reason': f'last line unreadable: {type(exc).__name__}'}


def ledger_tail(path):
    """The last line's hash, or None if the file is absent/empty/unreadable.

    Never a placeholder hash: a ledger that is not there has no tail.
    """
    p = Path(path)
    if not p.exists():
        return None
    try:
        lines = [l for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
    except OSError:
        return None
    if not lines:
        return None
    try:
        return json.loads(lines[-1]).get('hash')
    except Exception:
        return None


def resolve_ledger(meta, name):
    """The dialect's real ledger path.

    A dialect serving several bodies may declare one shared file (meshbot does);
    otherwise the convention is HERMES_HOME/<dialect>-protocol.jsonl.
    """
    p = _dialect_ledger(meta, name)
    if p is not None:
        return Path(p)
    module = meta.get('module') or ''
    dialect = module[:-len('_protocol')] if module.endswith('_protocol') else name
    return HERMES_HOME / f'{dialect}-protocol.jsonl'


def _display(path, base):
    """A path a human can act on: repo-relative, else home-relative, else absolute."""
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return str(path)


def dialect_evidence(name, meta=None):
    """Measured evidence about the dialect that serves robot `name`.

    Every field is read from disk. A missing file is None (0 bytes), never a
    guess. This is what `robot://doctor` and the robots index publish.
    """
    meta = meta or ROBOTS.get(name, {})
    module = meta.get('module')
    mod_path = HERE / f'{module}.py' if module else None
    src = mod_path.read_text(encoding='utf-8', errors='replace') \
        if mod_path and mod_path.is_file() else ''
    ledger = resolve_ledger(meta, name)
    # A tail hash is only checkable by a reader if the file ships with the estate.
    # Measured here, so the surface never presents an unverifiable hash as evidence.
    in_estate = bool(ledger.is_file()) and 'github-pages' in str(ledger).replace('\\', '/')
    return {
        'module': _display(mod_path, HERE.parent) if mod_path and mod_path.is_file() else None,
        'module_bytes': mod_path.stat().st_size if mod_path and mod_path.is_file() else 0,
        'verb_table_present': bool(src) and ('VERBS' in src) and ('def verbs' in src),
        'ledger_file': _display(ledger, HERMES_HOME),
        'ledger_bytes': ledger.stat().st_size if ledger.is_file() else 0,
        'ledger_tail': ledger_tail(ledger),
        'ledger_in_estate': in_estate,
    }


def _table_from_verbs(v):
    raw = v.get('verbs') if isinstance(v, dict) else None
    if not isinstance(raw, dict):
        return {}
    out = {}
    for name, meta in raw.items():
        if isinstance(meta, dict):
            out[name] = meta.get('class') or meta.get('cls') or 'unknown'
        else:
            out[name] = 'unknown'
    return out


def _verb_table(mod):
    """Uniform verb table: asimov nests `verbs`, reachy/microduck key it directly."""
    try:
        v = mod.verbs()
    except Exception:
        return {}
    return _table_from_verbs(v)


def _dialect_verbs(mod, meta, name):
    """A multi-body dialect reports per body; fall back to the module table."""
    fn = getattr(mod, 'verbs_for', None)
    if fn:
        try:
            return fn(meta.get('body') or name)
        except Exception:
            pass
    try:
        return mod.verbs()
    except Exception:
        return {}


def _dialect_ledger(meta, name):
    """A dialect serving several bodies may share one ledger file."""
    try:
        mod = _load(meta['module'])
    except Exception:
        return None
    fn = getattr(mod, 'ledger_path', None)
    if not fn:
        return None
    try:
        p = fn(meta.get('body') or name)
        return Path(p) if p else None
    except Exception:
        return None


def _policy_sha(table):
    """The policy IS the verb set. Hash it so a change is a measurable event."""
    return hashlib.sha256(_canonical(table).encode('utf-8')).hexdigest()


def discover():
    """Scan the estate for dialect modules that are NOT registered.

    Adding a robot should be one registry entry; this reports the ones we have
    missed, so the registry cannot silently lag the disk. Test modules are
    skipped, and a `*_protocol.py` that is really a generator (no SCHEME, no
    dispatch) is reported separately rather than as a missing robot.
    """
    # A dialect is registered when a ROSTER ENTRY uses it — not when its own name
    # is a roster key. `meshbot` serves Soldier, Xbot and kira, so keying off the
    # module name alone reported it as an unregistered gap: a false claim on a
    # page whose whole point is that gaps are named, never invented.
    used = {meta['module'][:-len('_protocol')]
            for meta in ROBOTS.values() if meta.get('module', '').endswith('_protocol')}
    found, others = {}, {}
    for path in sorted(HERE.glob('*_protocol.py')):
        module = path.stem
        name = module[:-len('_protocol')]
        if module == 'robot_protocol' or name.startswith('test'):
            continue
        entry = {'module': module, 'path': str(path), 'registered': name in used}
        try:
            mod = _load(module)
            entry['scheme'] = getattr(mod, 'SCHEME', None)
            entry['dispatch'] = hasattr(mod, 'dispatch')
            entry['status'] = hasattr(mod, 'status')
            entry['verbs'] = len(_verb_table(mod))
        except Exception as exc:
            entry['reason'] = f'{type(exc).__name__}: {exc}'
        if entry.get('scheme') and entry.get('dispatch'):
            found[name] = entry
        else:
            others[name] = entry
    return {'dialects': found, 'modules': others}


def doctor():
    """Probe every robot and every dialect. Measured, never asserted.

    The estate rule: a doctor runs, and the result is on the door. This reports
    presence, the verb table, the policy hash, the ledger tail and the
    transports — and it names the dialects on disk that the registry misses.
    """
    rows = {}
    for name, meta in ROBOTS.items():
        st = _robot_status(name, meta)
        row = {'robot': name, 'scheme': meta['scheme'], 'sdk': meta['sdk'],
               'present': st['present'], 'verb_count': st.get('verb_count'),
               'transports': st.get('transports'), 'live': st.get('live'),
               'ledger': _ledger_tail(name, meta),
               'evidence': dialect_evidence(name, meta)}
        try:
            mod = _load(meta['module'])
            table = _table_from_verbs(_dialect_verbs(mod, meta, name))
            row['verbs'] = len(table)
            row['classes'] = {c: sum(1 for v in table.values() if v == c)
                              for c in sorted(set(table.values()))}
            row['policy_sha256'] = _policy_sha(table)
        except Exception as exc:
            row['verbs'] = None
            row['reason'] = f'{type(exc).__name__}: {exc}'
        rows[name] = row
    disc = discover()
    unregistered = sorted(n for n, e in disc['dialects'].items() if not e['registered'])
    ok = all(r['present'] for r in rows.values())
    return {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'protocol': 'robot-protocol/1', 'ok': ok,
            'robots': rows, 'dialects_on_disk': disc['dialects'],
            'modules_on_disk': disc['modules'],
            'unregistered_dialects': unregistered,
            'rule': 'A doctor runs. A check that was not run is not shown as passing.'}


def authority():
    """The authority link: per robot, the gate classes and the grant shape.

    Presence is not permission. This reports what each dialect would refuse and
    what an approval would have to look like — it never grants anything.
    """
    out = {}
    for name, meta in ROBOTS.items():
        row = {'robot': name, 'scheme': meta['scheme'], 'grants': False}
        try:
            mod = _load(meta['module'])
            table = _table_from_verbs(_dialect_verbs(mod, meta, name))
            row['classes'] = {c: sum(1 for v in table.values() if v == c)
                              for c in sorted(set(table.values()))}
            row['motion_verbs'] = sum(1 for v in table.values()
                                      if v in ('motion', 'safety', 'high_power'))
            probe = next((v for v, c in table.items() if c in
                          ('motion', 'safety', 'high_power')), None)
            if probe and hasattr(mod, 'grant'):
                g = mod.grant(probe)
                row['probe_verb'] = probe
                row['grant'] = {'grants': g.get('grants'),
                                'required': g.get('required')}
                row['refused_without_approval'] = True
            else:
                row['grant'] = None
        except Exception as exc:
            row['reason'] = f'{type(exc).__name__}: {exc}'
        out[name] = row
    return {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'robots': out, 'granted': False,
            'rule': 'An address is not a permission. Motion needs approval or an armed deadman.'}


def _resolve(route):
    """Robot names are case-sensitive on disk (Soldier, Xbot) but an address
    should not fail because a caller lowercased it."""
    if route in ROBOTS:
        return route
    for k in ROBOTS:
        if k.lower() == route:
            return k
    return None


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
    if route == 'fleet' and args == ['authority']:
        return _record(raw, None, authority())
    if route == 'doctor':
        return _record(raw, None, doctor())
    if route in FLEET_ROUTES:
        return _record(raw, None, fleet())
    name = _resolve(route)
    if name is None:
        return _record(raw, None, {'success': False, 'refused': True, 'scheme': SCHEME,
                                   'authority': AUTHORITY, 'address': raw,
                                   'reason': f'unknown robot {route!r}',
                                   'robots': sorted(ROBOTS)})
    meta = ROBOTS[name]
    sub_route = ' '.join(args)
    try:
        mod = _load(meta['module'])
    except Exception as exc:
        return _record(raw, name, {'success': False, 'refused': True, 'scheme': SCHEME,
                                   'authority': AUTHORITY, 'robot': name,
                                   'reason': f'dialect {meta["module"]} did not import: {exc}'})
    # a dialect that serves several bodies exposes dispatch_for(name, route)
    fn = getattr(mod, 'dispatch_for', None)
    if fn:
        out = fn(meta.get('body') or name, sub_route)
    else:
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
