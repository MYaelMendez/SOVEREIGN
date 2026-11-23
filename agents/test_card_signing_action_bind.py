"""Task 1 (tinyACTOR): a card must bind the EXACT action, not just the verb.

Defect D1: _canonical signs {verb, task_id, subject, expires_at, nonce} with no
action hash. A card minted for action X therefore verifies for action Y with the
same verb — replay across intents, the exact failure æ Policy exists to prevent.
"""
from __future__ import annotations

import hashlib, importlib.util, json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    'card_signing', 'C:/æ/agents/card_signing.py')
cs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cs)


def _pub_from_private():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization as ser
    priv = Ed25519PrivateKey.from_private_bytes(cs.load_private())
    return priv.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)


ACTION_X = {'verb': 'set_velocity', 'args': {'v': 0.5}, 'scene': 'rehearsal-A'}
ACTION_Y = {'verb': 'set_velocity', 'args': {'v': 9.9}, 'scene': 'rehearsal-B'}


def test_card_for_action_x_fails_for_action_y():
    card = cs.sign_card_for_action(ACTION_X, ttl=60)
    assert cs.verify_card_for_action(card, ACTION_X, public_key=_pub_from_private())['ok'] is True
    other = cs.verify_card_for_action(card, ACTION_Y, public_key=_pub_from_private())
    assert other['ok'] is False
    assert 'action' in other['reason'].lower()


def test_action_hash_is_in_canonical_payload():
    card = cs.sign_card_for_action(ACTION_X, ttl=60)
    assert card['action_sha256'] == hashlib.sha256(
        json.dumps(ACTION_X, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def test_legacy_card_still_verifies():
    """Old cards (no action hash) must not be invalidated by this change."""
    old = cs.sign_card('probe', ttl=60)
    assert cs.verify_card(old, public_key=_pub_from_private())['ok'] is True


def test_tampered_action_is_refused():
    card = cs.sign_card_for_action(ACTION_X, ttl=60)
    tampered = dict(ACTION_X, args={'v': 100.0})
    assert cs.verify_card_for_action(card, tampered, public_key=_pub_from_private())['ok'] is False
