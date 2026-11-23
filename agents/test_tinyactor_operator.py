"""Task 3 (tinyACTOR): operator pane is fail-closed until a human binds."""
from __future__ import annotations

import importlib.util, json
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location('tinyactor_operator',
                                             'C:/æ/agents/tinyactor_operator.py')
op = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(op)


def test_unbound_status_refuses_and_never_grants(monkeypatch, tmp_path):
    monkeypatch.setattr(op, 'BINDING', tmp_path / 'missing.json')
    s = op.status()
    assert s['bound'] is False
    assert s['grants'] is False
    assert 'operator not bound' in s['reason']


def test_prepare_mints_nothing_when_unbound(monkeypatch, tmp_path):
    monkeypatch.setattr(op, 'BINDING', tmp_path / 'missing.json')
    r = op.prepare({'verb': 'set_velocity', 'args': {'v': 0.5}})
    assert r['refused'] is True
    assert r['minted'] is False
    assert r['granted'] is False


def test_verify_never_defaults_a_public_key(monkeypatch, tmp_path):
    monkeypatch.setattr(op, 'BINDING', tmp_path / 'missing.json')
    r = op.verify({'sig': 'x'}, {'verb': 'set_velocity'})
    assert r['valid'] is False and r['granted'] is False
    assert 'operator not bound' in r['reason']


def test_no_stub_cast_in_module_source():
    text = Path('C:/æ/agents/tinyactor_operator.py').read_text(encoding='utf-8')
    assert 'default_actor' not in text
    assert 'grants: True' not in text


def test_verify_always_carries_granted_and_grants(monkeypatch, tmp_path):
    """A verified card must never be mistaken for this surface granting."""
    monkeypatch.setattr(op, 'BINDING', tmp_path / 'missing.json')
    r = op.verify({'sig': 'x'}, {'verb': 'set_velocity'})
    assert 'granted' in r and r['granted'] is False
    assert 'grants' in r and r['grants'] is False


def test_hex_public_key_is_not_treated_as_a_path(monkeypatch, tmp_path):
    """Ed25519 pubkey hex is 64 chars; the old >128 heuristic read it as a path."""
    import json as _json
    cs = op.card_signing()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization as ser
    pub = Ed25519PrivateKey.from_private_bytes(cs.load_private()).public_key().public_bytes(
        ser.Encoding.Raw, ser.PublicFormat.Raw).hex()
    b = tmp_path / 'binding.json'
    b.write_text(_json.dumps({'operator': 'HUMAN://ROOT', 'public_key': pub,
        'actor': 'asimov', 'bound_by': 'HUMAN://ROOT', 'bound_at': '2026-11-23T00:00:00Z'}))
    monkeypatch.setattr(op, 'BINDING', b)
    action = {'verb': 'set_velocity', 'args': {'v': 0.5}}
    card = cs.sign_card_for_action(action, ttl=60)
    r = op.verify(card, action)
    assert r['valid'] is True, r.get('reason')
    assert r['granted'] is False
