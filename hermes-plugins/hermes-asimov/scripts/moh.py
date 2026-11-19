"""moh:// — Mixture of Harnesses, routed by compute scale.

Extends hermes-ae/harness-registry/v1 (nine harnesses, each with a receipted
degraded mode) with two things it does not carry: AGENTS and SCALES.

    moh://                     the registry: agents, scales, harness mixes
    moh://agents               five orchestrators, wætz conducting
    moh://agent <id>           one agent's mix, scale and delegation rights
    moh://route <agent> <h>    resolve a harness to a device + fallback
    moh://delegate <a> <b> <h> may A ask B to run harness h?  (never grants)
    moh://scales               addressable compute, measured vs declared

The human is a NODE, not a caller: wætz is the twin, inside the policy, with a
scale and a harness mix like everyone else — and still not a signature.

A harness may degrade. It may never lie about which mode served. Every route
records the device in its receipt.

Authority: HUMAN://ROOT.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEME = 'moh://'
AUTHORITY = 'HUMAN://ROOT'
HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
H = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
MOH = Path(os.environ.get('HERMES_ASIMOV_MOH', PLUGIN / 'moh.json'))
V1 = H / 'plugins' / 'hermes-ae' / 'harnesses.json'
LEDGER = Path(os.environ.get('HERMES_MOH_LEDGER', H / 'moh-receipts.jsonl'))


def _canon(o: Any) -> str:
    return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _head() -> str:
    if LEDGER.exists():
        lines = [l for l in LEDGER.read_text(encoding='utf-8').splitlines() if l.strip()]
        if lines:
            try:
                return str(json.loads(lines[-1])['hash'])
            except Exception:
                pass
    return '0' * 64


def receipt(action: str, detail: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        'ts': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'action': action, 'authority': AUTHORITY, 'detail': detail, 'prev': _head()}
    body['hash'] = hashlib.sha256(_canon(body).encode('utf-8')).hexdigest()
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open('a', encoding='utf-8') as fh:
        fh.write(_canon(body) + '\n')
    return body


def load() -> tuple[dict[str, Any] | None, str | None]:
    """Load v2 and resolve the v1 harness definitions it extends. Fail closed."""
    if not MOH.exists():
        return None, f'moh registry missing: {MOH}'
    try:
        reg = json.loads(MOH.read_text(encoding='utf-8'))
    except Exception as exc:
        return None, f'moh registry unparseable: {exc}'
    if reg.get('schema') != 'hermes-asimov/moh/2':
        return None, f'unknown schema {reg.get("schema")!r}'
    if not V1.exists():
        return None, f'base harness registry missing: {V1}'
    try:
        base = json.loads(V1.read_text(encoding='utf-8'))
    except Exception as exc:
        return None, f'base registry unparseable: {exc}'
    harnesses = {h['name']: h for h in base.get('harnesses', [])}
    reg['_harnesses'] = harnesses
    ids = [a['id'] for a in reg.get('agents', [])]
    if len(ids) != len(set(ids)):
        return None, 'duplicate agent ids'
    if reg.get('center') not in ids:
        return None, f'center {reg.get("center")!r} is not a registered agent'
    for a in reg['agents']:
        for h in a.get('harnesses', []):
            if h not in harnesses:
                return None, f'agent {a["id"]} names unknown harness {h!r}'
        if a.get('default_scale') not in reg.get('scales', {}):
            return None, f'agent {a["id"]} names unknown scale {a.get("default_scale")!r}'
        for d in a.get('may_delegate_to', []):
            if d not in ids:
                return None, f'agent {a["id"]} may_delegate_to unknown agent {d!r}'
    return reg, None


def _refuse(reason: str, **extra: Any) -> dict[str, Any]:
    return {'success': False, 'refused': True, 'scheme': SCHEME,
            'authority': AUTHORITY, 'reason': reason, **extra}


def overview() -> dict[str, Any]:
    reg, err = load()
    if err:
        return _refuse(err)
    assert reg is not None
    return {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'schema': reg['schema'], 'extends': reg['extends'],
            'base_runtime': reg['base_runtime'], 'center': reg['center'],
            'agents': len(reg['agents']), 'harnesses': len(reg['_harnesses']),
            'scales': list(reg['scales']),
            'principles': reg['principles'],
            'note': 'Every agent defaults to hermes-agent. Specialisation is a harness mix.'}


def agents() -> dict[str, Any]:
    reg, err = load()
    if err:
        return _refuse(err)
    assert reg is not None
    out = []
    for a in reg['agents']:
        out.append({'id': a['id'], 'title': a['title'], 'role': a['role'],
                    'scale': a['default_scale'], 'harnesses': a['harnesses'],
                    'may_delegate_to': a['may_delegate_to'], 'authority': a['authority'],
                    'conductor': a['id'] == reg['center']})
    return {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'base_runtime': reg['base_runtime'], 'count': len(out), 'agents': out}


def agent(aid: str) -> dict[str, Any]:
    reg, err = load()
    if err:
        return _refuse(err)
    assert reg is not None
    a = next((x for x in reg['agents'] if x['id'] == aid), None)
    if not a:
        return _refuse(f'unknown agent {aid!r}', available=[x['id'] for x in reg['agents']])
    mix = []
    for name in a['harnesses']:
        h = reg['_harnesses'][name]
        mix.append({'harness': name, 'receipt': h.get('receipt_action'),
                    'runtime': h.get('runtime'), 'fallback': h.get('fallback'),
                    'scale': a['default_scale']})
    return {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'agent': a, 'mix': mix, 'base_runtime': reg['base_runtime'],
            'conductor': a['id'] == reg['center'],
            'note': 'A harness may degrade; the receipt records which mode served.'}


def route(aid: str, harness: str, scale: str | None = None) -> dict[str, Any]:
    reg, err = load()
    if err:
        return _refuse(err)
    assert reg is not None
    a = next((x for x in reg['agents'] if x['id'] == aid), None)
    if not a:
        return _refuse(f'unknown agent {aid!r}')
    if harness not in a['harnesses']:
        return _refuse(f'agent {aid!r} does not carry harness {harness!r}',
                       carries=a['harnesses'])
    h = reg['_harnesses'][harness]
    sc = scale or a['default_scale']
    if sc not in reg['scales']:
        return _refuse(f'unknown scale {sc!r}', available=list(reg['scales']))
    s = reg['scales'][sc]
    degraded = not s.get('measured', False)
    out = {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
           'agent': aid, 'harness': harness, 'scale': sc, 'device': s['device'],
           'tier': s['tier'], 'measured': s.get('measured', False),
           'runtime': h.get('runtime'), 'receipt_action': h.get('receipt_action'),
           'mode': 'declared' if degraded else 'measured',
           'fallback': h.get('fallback') if degraded else None,
           'grants': False,
           'note': ('Scale is declared, not probed in this session; the fallback applies '
                    'and the receipt records the degraded mode.' if degraded else
                    'Scale measured on this host.')}
    out['receipt'] = receipt('MOH://DEGRADED' if degraded else 'MOH://ROUTE',
                             {'agent': aid, 'harness': harness, 'scale': sc,
                              'device': s['device'], 'mode': out['mode']})
    return out


def delegate(src: str, dst: str, harness: str) -> dict[str, Any]:
    """May src ask dst to run a harness? Reports the shape. GRANTS NOTHING."""
    reg, err = load()
    if err:
        return _refuse(err)
    assert reg is not None
    a = next((x for x in reg['agents'] if x['id'] == src), None)
    b = next((x for x in reg['agents'] if x['id'] == dst), None)
    if not a or not b:
        return _refuse('unknown agent in delegation')
    allowed = dst in a.get('may_delegate_to', [])
    carries = harness in b['harnesses']
    ok = allowed and carries
    out = {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
           'from': src, 'to': dst, 'harness': harness,
           'permitted': ok, 'grants': False,
           'reasons': ([] if allowed else [f'{src} may not delegate to {dst}']) +
                      ([] if carries else [f'{dst} does not carry {harness}']),
           'note': 'Delegation is a proposal. Motion still needs HUMAN://ROOT.'}
    out['receipt'] = receipt('MOH://DELEGATE',
                             {'from': src, 'to': dst, 'harness': harness, 'permitted': ok})
    return out


def scales() -> dict[str, Any]:
    reg, err = load()
    if err:
        return _refuse(err)
    assert reg is not None
    return {'success': True, 'scheme': SCHEME, 'authority': AUTHORITY,
            'scales': reg['scales'],
            'note': 'measured=true means probed on this host; false means declared only.'}


def dispatch(raw: str) -> dict[str, Any]:
    s = raw.strip()
    if s.startswith(SCHEME):
        s = s[len(SCHEME):]
    p = s.split()
    r = p[0].lower() if p else ''
    if r in ('', 'status'):
        return overview()
    if r == 'agents':
        return agents()
    if r == 'agent':
        return agent(p[1]) if len(p) > 1 else _refuse('agent id required')
    if r == 'scales':
        return scales()
    if r == 'route':
        if len(p) < 3:
            return _refuse('usage: moh://route <agent> <harness> [scale]')
        return route(p[1], p[2], p[3] if len(p) > 3 else None)
    if r == 'delegate':
        if len(p) < 4:
            return _refuse('usage: moh://delegate <from> <to> <harness>')
        return delegate(p[1], p[2], p[3])
    return _refuse(f'unknown route {r!r}',
                   routes=['', 'agents', 'agent', 'scales', 'route', 'delegate'])


if __name__ == '__main__':
    print(json.dumps(dispatch(' '.join(sys.argv[1:]) or SCHEME), ensure_ascii=False))
