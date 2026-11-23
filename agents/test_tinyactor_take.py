"""Task 4 (tinyACTOR): takes are human-directed and never auto-chain."""
from __future__ import annotations

import importlib.util, json, tempfile
from pathlib import Path
import pytest

S = importlib.util.spec_from_file_location('tk', 'C:/æ/agents/tinyactor_take.py')
tk = importlib.util.module_from_spec(S); S.loader.exec_module(tk)
OP = importlib.util.spec_from_file_location('op', 'C:/æ/agents/tinyactor_operator.py')
op = importlib.util.module_from_spec(OP); OP.loader.exec_module(op)
cs = op.card_signing()

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization as ser

TAKE = {'scene': 'rehearsal-A', 'verb': 'set_velocity', 'args': {'v': 0.5},
        'start': 0.0, 'end': 2.0, 'camera': 'front-916'}


def _use_op(monkeypatch, path):
    op.BINDING = path
    monkeypatch.setattr(tk, 'OPERATOR_MOD', op)


def _bind(tmp_path):
    pub = Ed25519PrivateKey.from_private_bytes(cs.load_private()).public_key().public_bytes(
        ser.Encoding.Raw, ser.PublicFormat.Raw).hex()
    b = tmp_path / 'binding.json'
    b.write_text(json.dumps({'operator': 'HUMAN://ROOT', 'public_key': pub,
        'actor': 'asimov', 'bound_by': 'HUMAN://ROOT', 'bound_at': '2026-11-23T00:00:00Z'}))
    return b


def test_unbound_take_is_refused(monkeypatch, tmp_path):
    _use_op(monkeypatch, tmp_path / 'missing.json')
    r = tk.record(TAKE, {'sig': 'x'})
    assert r['refused'] and not r['recorded'] and not r['granted']


def test_bound_take_records_once(monkeypatch, tmp_path):
    _use_op(monkeypatch, _bind(tmp_path))
    monkeypatch.setattr(tk, 'LEDGER', tmp_path / 'takes.jsonl')
    card = cs.sign_card_for_action({'verb': TAKE['verb'], 'args': TAKE['args'],
                                    'scene': TAKE['scene']}, ttl=60)
    r = tk.record(TAKE, card)
    assert r['decision'] == 'RECORDED' and r['recorded']
    assert tk.status()['count'] == 1


def test_second_take_on_one_card_is_refused(monkeypatch, tmp_path):
    """No auto-chaining: the thesis of operated-not-orchestrated."""
    _use_op(monkeypatch, _bind(tmp_path))
    monkeypatch.setattr(tk, 'LEDGER', tmp_path / 'takes.jsonl')
    card = cs.sign_card_for_action({'verb': TAKE['verb'], 'args': TAKE['args'],
                                    'scene': TAKE['scene']}, ttl=60)
    first = tk.record(TAKE, card)
    second = tk.record(dict(TAKE, start=3.0), card)
    assert first['recorded'] and second['refused']
    assert 'auto-chaining' in second['reason']
    assert tk.status()['count'] == 1


def test_wrong_action_card_is_refused(monkeypatch, tmp_path):
    _use_op(monkeypatch, _bind(tmp_path))
    monkeypatch.setattr(tk, 'LEDGER', tmp_path / 'takes.jsonl')
    card = cs.sign_card_for_action({'verb': 'set_velocity', 'args': {'v': 9.9},
                                    'scene': 'another'}, ttl=60)
    r = tk.record(TAKE, card)
    assert r['refused'] and not r['recorded']


def test_take_chain_integrity(monkeypatch, tmp_path):
    _use_op(monkeypatch, _bind(tmp_path))
    monkeypatch.setattr(tk, 'LEDGER', tmp_path / 'takes.jsonl')
    card = cs.sign_card_for_action({'verb': TAKE['verb'], 'args': TAKE['args'],
                                    'scene': TAKE['scene']}, ttl=60)
    tk.record(TAKE, card)
    assert tk.status()['chain_ok']
