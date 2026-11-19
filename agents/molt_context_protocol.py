#!/usr/bin/env python3
"""æææ://molt_context_protocol — MCP/1517, the context handshake.

Plain MCP exposes tools. It has no answer to the question that matters when
agents compose: **whose intent is this, and did authority come with it?**

MCP/1517 answers both. Context flows. Authority does not.

    æææ://molt_context_protocol                 protocol status + the contract
    æææ://molt_context_protocol handshake       offer provenance, receive context
    æææ://molt_context_protocol verify <id>     is this agent human-verified?
    æææ://molt_context_protocol molt <id>       advance the molt cycle

THE RULE (from AGENTS.md, not invented here)
    "Scanning, nesting and forking do not transfer authority."

    A child agent inherits CONTEXT — the brief, the cast, the conventions.
    It never inherits the SIGNATURE. Every physical act still needs the human.
    This is why a fleet can be given everything and still be unable to move.

THE HANDSHAKE
    1. offer      agent presents {agent_id, principal, pledge_sha, capability}
    2. check      pledge must be committed; principal must be declared
    3. transfer   context is released; grants stay false
    4. receipt    SHA-256 over the exchange, chained to the previous

    An agent with no declared principal is REFUSED, not defaulted. Anonymous
    automation is worthless — every agent needs a verifiable human origin.

THE MOLT CYCLE
    Discover -> Steep -> Serve -> Molt -> Garden -> infinity

    Molt is the only transition that requires a human: shedding the old context
    is an authority decision, not an optimisation.

HONESTY
    This is the protocol layer, not a network service. It reads local ledgers
    and writes local receipts. No transport is implemented; nothing here binds
    a socket. `verify` reports what the ledger says, not what it hopes.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from pathlib import Path

VERSION = 'MCP/1517'
CYCLE = ['discover', 'steep', 'serve', 'molt', 'garden']
HUMAN_GATED = {'molt'}          # shedding context is an authority decision


def home() -> Path:
    return Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))


def state_path() -> Path:
    return home() / 'molt-context.json'


def load() -> dict:
    p = state_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'version': VERSION, 'agents': {}, 'chain': [], 'prev': '0' * 64}


def save(d: dict) -> None:
    state_path().write_text(json.dumps(d, indent=2), encoding='utf-8')


def receipt(d: dict, intent: str, payload: dict) -> str:
    """H(prev || intent || payload). A handshake with no receipt did not happen."""
    body = json.dumps({'intent': intent, 'payload': payload}, sort_keys=True)
    h = hashlib.sha256((d['prev'] + body).encode('utf-8')).hexdigest()
    d['chain'].append({'sha': h, 'intent': intent, 'ts': time.time()})
    d['prev'] = h
    return h


def pledge_sha(agent_id: str) -> str | None:
    """Read the committed pledge from the real store.

    agent_pledge.py writes ONE file — kænbæn/agent-pledge.json — with a
    `commitments` map keyed by agent id. There is no per-agent pledges/ dir.
    A missing commitment is a refusal, never a default.
    """
    base = Path(os.environ.get('KAENBAEN_BASE', r'C:\æ\kænbæn'))
    f = base / 'agent-pledge.json'
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        return None
    c = (d.get('commitments') or {}).get(agent_id)
    if not c:
        return None
    return c.get('pledge_hash') or d.get('pledge_hash')


def context_bundle() -> dict:
    """What a child inherits. Everything here is safe to publish."""
    return {
        'chassis': 'æ://',
        'prompt': '>_æ://',
        'design': {'gold': '#D4AF37', 'void': '#050505'},
        'cycle': CYCLE,
        'rules': [
            'Claim before you act.',
            'Commit to the pledge.',
            'Verify before you claim.',
            'Never move a secret.',
        ],
        'verdicts': ['allow', 'require_approval', 'deny'],
        'law': 'Scanning, nesting and forking do not transfer authority.',
        'cast': ['nous', 'hermes', 'menlo', 'asimov', 'waetz'],
    }


def handshake(offer: dict) -> dict:
    d = load()
    aid = (offer.get('agent_id') or '').strip()
    principal = (offer.get('principal') or '').strip()
    if not aid:
        return {'ok': False, 'refused': True, 'decision': 'deny',
                'rules': ['MCP-001'], 'reason': 'no agent_id offered',
                'grants': False}
    if not principal:
        # anonymous automation is worthless — refuse rather than default
        return {'ok': False, 'refused': True, 'decision': 'deny',
                'rules': ['MCP-002', 'AUTH-001'],
                'reason': 'no human principal declared. Agent provenance is required.',
                'agent_id': aid, 'grants': False}
    ps = offer.get('pledge_sha') or pledge_sha(aid)
    if not ps:
        return {'ok': False, 'refused': True, 'decision': 'require_approval',
                'rules': ['MCP-003'],
                'reason': 'pledge not committed. Run: agent_pledge.py commit --agent ' + aid,
                'agent_id': aid, 'principal': principal, 'grants': False}
    rec = {'agent_id': aid, 'principal': principal, 'pledge_sha': ps,
           'capability': offer.get('capability', []), 'stage': 'discover',
           'handshaked_at': time.time(), 'version': VERSION}
    d['agents'][aid] = rec
    sha = receipt(d, 'handshake', rec)
    save(d)
    return {'ok': True, 'version': VERSION, 'agent_id': aid, 'principal': principal,
            'pledge_sha': ps[:16], 'stage': 'discover',
            'context': context_bundle(),
            # the whole point: context transferred, authority did not
            'grants': False, 'authority': principal,
            'executed': False, 'receipt': sha,
            'note': 'Context flows. Authority does not. Every act still needs the human.'}


def verify(aid: str) -> dict:
    d = load()
    a = d['agents'].get(aid)
    if not a:
        return {'ok': False, 'verified': False, 'agent_id': aid,
                'reason': 'no handshake on record. Not refused — simply unknown.',
                'grants': False}
    return {'ok': True, 'verified': bool(a.get('principal')),
            'agent_id': aid, 'principal': a['principal'],
            'pledge_sha': a['pledge_sha'][:16], 'stage': a['stage'],
            'version': a['version'], 'grants': False,
            'note': 'verified means a human principal is on record, not that the agent is trusted'}


def molt(aid: str, to: str | None = None) -> dict:
    d = load()
    a = d['agents'].get(aid)
    if not a:
        return {'ok': False, 'refused': True, 'decision': 'deny', 'rules': ['MCP-004'],
                'reason': 'unknown agent; handshake first', 'grants': False}
    cur = a['stage']
    nxt = to or CYCLE[(CYCLE.index(cur) + 1) % len(CYCLE)]
    if nxt not in CYCLE:
        return {'ok': False, 'refused': True, 'decision': 'deny', 'rules': ['MCP-005'],
                'reason': f'unknown stage {nxt!r}', 'cycle': CYCLE, 'grants': False}
    if nxt in HUMAN_GATED:
        # shedding context is an authority decision, not an optimisation
        return {'ok': False, 'refused': True, 'decision': 'require_approval',
                'rules': ['MCP-006', 'AUTH-002'], 'agent_id': aid,
                'from': cur, 'to': nxt, 'executed': False, 'grants': False,
                'reason': 'molt sheds context. Only the human principal may authorise it.'}
    a['stage'] = nxt
    sha = receipt(d, 'molt', {'agent_id': aid, 'from': cur, 'to': nxt})
    save(d)
    return {'ok': True, 'agent_id': aid, 'from': cur, 'to': nxt,
            'cycle': CYCLE, 'receipt': sha, 'grants': False}


def status() -> dict:
    d = load()
    return {'ok': True, 'scheme': 'æææ://molt_context_protocol', 'version': VERSION,
            'agents': len(d['agents']), 'receipts': len(d['chain']),
            'cycle': CYCLE, 'human_gated': sorted(HUMAN_GATED),
            'law': 'Scanning, nesting and forking do not transfer authority.',
            'usage': ['handshake', 'verify <agent_id>', 'molt <agent_id> [stage]'],
            'transport': 'NOT IMPLEMENTED — local ledgers only, no socket bound',
            'grants': False}


def main():
    ap = argparse.ArgumentParser(prog='molt_context_protocol')
    ap.add_argument('action', nargs='?', default='status')
    ap.add_argument('arg', nargs='?')
    ap.add_argument('arg2', nargs='?')
    ap.add_argument('--agent', help='agent_id for handshake')
    ap.add_argument('--principal', help='human principal, e.g. HUMAN://ROOT')
    ap.add_argument('--capability', default='')
    a = ap.parse_args()
    act = a.action.lower()
    if act == 'handshake':
        res = handshake({'agent_id': a.arg or a.agent, 'principal': a.principal,
                         'capability': [c for c in a.capability.split(',') if c]})
    elif act == 'verify':
        res = verify(a.arg or a.agent or '')
    elif act == 'molt':
        res = molt(a.arg or a.agent or '', a.arg2)
    else:
        res = status()
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
