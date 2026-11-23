#!/usr/bin/env python3
"""
tinyACTOR operator authority — Task 3 (interim, fail-closed).

The operator console is the ONLY pane that may arm a grant. Until HUMAN://ROOT
is bound (identity + public key + first actor), every prepare/verify call
returns an explicit refusal naming what is missing. There is NO stub grant,
NO default operator, NO silent fallback.

Binding file: C:/æ/secrets/tinyactor-operator.json  (custody, never public)
  {'operator': '<human id>', 'public_key': '<hex Ed25519 public key path or hex>',
   'actor': '<robot>', 'bound_by': '<human>', 'bound_at': '<ISO>'}

  status()            current binding state, refusal if unbound
  prepare(action)     hash + policy evaluate; MINTS NOTHING; grants:false
  verify(card,action) bound-card verification; refuses when unbound
"""
from __future__ import annotations

import hashlib, importlib.util, json, os
from pathlib import Path

BINDING = Path(os.environ.get(
    'TINYACTOR_BINDING', 'C:/æ/secrets/tinyactor-operator.json'))
POLICY = Path('C:/æ/github-pages/ae-policy.json')
CS = Path('C:/æ/agents/card_signing.py')


def _mod(path: Path, name: str):
    s = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


def card_signing():
    return _mod(CS, 'tinyactor_card_signing')


def binding() -> dict:
    if not BINDING.exists():
        return {'ok': False, 'bound': False,
                'reason': f'operator not bound — missing {BINDING}',
                'requires': ['operator', 'public_key', 'actor', 'bound_by', 'bound_at']}
    try:
        d = json.loads(BINDING.read_text(encoding='utf-8'))
    except Exception as e:
        return {'ok': False, 'bound': False, 'reason': f'binding unreadable: {e}'}
    missing = [k for k in ('operator','public_key','actor','bound_by','bound_at')
               if not d.get(k)]
    if missing:
        return {'ok': False, 'bound': False,
                'reason': 'binding incomplete: ' + ', '.join(missing), 'requires': missing}
    return {'ok': True, 'bound': True, 'binding': d,
            'sha256': hashlib.sha256(BINDING.read_bytes()).hexdigest()}


def status() -> dict:
    b = binding()
    pol = json.loads(POLICY.read_text(encoding='utf-8'))
    return {'ok': True, 'scheme': 'asimov://take', 'authority': 'HUMAN://ROOT',
            'bound': b['bound'], 'reason': b.get('reason'),
            'grants': False, 'policy_sha256': hashlib.sha256(POLICY.read_bytes()).hexdigest(),
            'rules': len(pol['rules']),
            'note': 'one authority pane; no grant button anywhere else'}


def prepare(action: dict) -> dict:
    """Hash + evaluate. NEVER mints a card, NEVER grants authority."""
    b = binding()
    if not b['bound']:
        return {'ok': True, 'refused': True, 'decision': 'REFUSE', 'granted': False,
                'grants': False, 'reason': b['reason'], 'minted': False}
    cs = card_signing()
    ahash = cs.action_hash(action)
    return {'ok': True, 'refused': False, 'decision': 'PROPOSE', 'granted': False,
            'grants': False, 'minted': False, 'action_sha256': ahash,
            'requires': 'human signs ' + ahash, 'binding_sha256': b['sha256']}


def verify(card: dict, action: dict) -> dict:
    """Verify a bound card. Unbound -> explicit refusal, never a default key.

    Single exit: every response carries valid/granted/grants=False. A verified
    card binds an action; it never makes THIS surface an authority.
    """
    out = {'ok': True, 'refused': True, 'valid': False,
           'granted': False, 'grants': False}
    b = binding()
    if not b['bound']:
        return {**out, 'reason': b['reason']}
    cs = card_signing()
    pub_hex = b['binding']['public_key']
    try:
        ph = pub_hex.strip()
        # Inline 64-char Ed25519 hex, or a PATH to a file containing hex text.
        p = Path(ph)
        if len(ph) == 64 and not p.exists():
            pub = bytes.fromhex(ph)
        elif p.exists():
            txt = p.read_text(encoding='ascii', errors='replace').strip()
            try:
                pub = bytes.fromhex(txt)          # the custody .pub is hex text
            except ValueError:
                pub = p.read_bytes()              # raw 32-byte key file
        else:
            return {**out, 'reason': f'public key not found: {ph}'}
    except Exception as e:
        return {**out, 'reason': f'public key unreadable: {e}'}
    r = cs.verify_card_for_action(card, action, public_key=pub)
    return {**out, 'refused': not r['ok'], 'valid': r['ok'], 'reason': r['reason'],
            'note': 'card bound to this action; authority stays in HUMAN://ROOT'}
