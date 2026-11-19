"""The deadman switch — Wætz's first rule, made enforceable.

    "no body moves while the human is away"

cast.json declared `motion_requires: human_approval_or_armed_deadman` from the
start. These tests make that string a checked property.

The critical property is FAIL CLOSED: no camera, no face, stale heartbeat,
unreadable record — every one must refuse. Absence of evidence is never
presence.
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tinypython as TP


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Each test gets its own deadman record — never the operator's real one."""
    monkeypatch.setenv('TINYPYTHON_DEADMAN', str(tmp_path / 'deadman.json'))
    return tmp_path / 'deadman.json'


# ── fail closed ─────────────────────────────────────────────────────────────

def test_unarmed_refuses_motion(isolated):
    g = TP.deadman_gate('move')
    assert g['refused'] is True
    assert 'DEAD-001' in g['rules'], 'absence of a heartbeat must add the deadman rule'
    assert g['presence'] is False
    assert g['grants'] is False and g['executed'] is False


def test_unarmed_reason_is_the_rule(isolated):
    g = TP.deadman_gate('move')
    assert 'no body moves while the human is away' in g['reason']


def test_unreadable_record_is_not_presence(isolated):
    isolated.write_text('{ this is not json', encoding='utf-8')
    p = TP.presence()
    assert p['present'] is False
    assert 'unreadable' in p['reason']


def test_missing_record_is_not_presence(isolated):
    assert TP.presence()['present'] is False


def test_record_without_timestamp_is_not_presence(isolated):
    isolated.write_text(json.dumps({'source': 'manual'}), encoding='utf-8')
    assert TP.presence()['present'] is False, 'a record with no armed_at must not read as present'


# ── simulation is never gated by presence ───────────────────────────────────

@pytest.mark.parametrize('intent', ['simulate', 'walk', 'trace', 'plan', 'observe'])
def test_thinking_needs_no_presence(isolated, intent):
    g = TP.deadman_gate(intent)
    assert g['decision'] == 'allow'
    assert g['grants'] is False
    assert g['executed'] is False


# ── the heartbeat ───────────────────────────────────────────────────────────

def test_arm_then_present(isolated):
    r = TP.arm(ttl=5.0)
    assert r['ok'] and r['armed']
    assert r['grants'] is False, 'arming records presence, it does not grant'
    assert TP.presence()['present'] is True


def test_heartbeat_expires(isolated):
    TP.arm(ttl=0.3)
    assert TP.presence()['present'] is True
    time.sleep(0.5)
    p = TP.presence()
    assert p['present'] is False
    assert 'stale' in p['reason']


def test_expiry_reinstates_the_deadman_rule(isolated):
    TP.arm(ttl=0.3)
    assert 'DEAD-001' not in TP.deadman_gate('move')['rules']
    time.sleep(0.5)
    assert 'DEAD-001' in TP.deadman_gate('move')['rules']


def test_disarm_withdraws_presence(isolated):
    TP.arm(ttl=60)
    assert TP.presence()['present'] is True
    TP.disarm()
    assert TP.presence()['present'] is False
    assert 'DEAD-001' in TP.deadman_gate('move')['rules']


# ── presence is not a signature ─────────────────────────────────────────────

def test_present_still_requires_approval(isolated):
    """The central property: presence removes ONE refusal, not both."""
    TP.arm(ttl=60)
    g = TP.deadman_gate('move')
    assert g['presence'] is True
    assert g['refused'] is True, 'a present human is not a signature'
    assert g['decision'] == 'require_approval'
    assert 'ACT-001' in g['rules'] and 'AUTH-002' in g['rules']
    assert 'DEAD-001' not in g['rules'], 'presence should remove only the deadman rule'
    assert g['grants'] is False and g['executed'] is False


def test_no_path_grants(isolated):
    """No combination of presence states may produce grants:true."""
    for ttl in (0.0, 0.3, 60.0):
        TP.arm(ttl=ttl)
        for intent in ('move', 'stand', 'simulate', 'walk'):
            g = TP.deadman_gate(intent)
            assert g['grants'] is False
            assert g['executed'] is False
        assert TP.presence()['grants'] is False
    assert TP.disarm()['grants'] is False


# ── the sensor ──────────────────────────────────────────────────────────────

def test_sense_reports_a_measurement_not_an_assumption():
    """Whatever the camera does, the result must carry a reason and grants:false."""
    s = TP.sense(timeout_s=0.5)
    assert 'present' in s and isinstance(s['present'], bool)
    assert 'reason' in s and s['reason']
    assert s['grants'] is False
    assert s['sensor'] == 'opencv-haar'


def test_camera_arm_refuses_without_a_face(isolated, monkeypatch):
    """A camera arm with no face must refuse, never fall back to manual."""
    monkeypatch.setattr(TP, 'sense', lambda *a, **k: {'present': False, 'reason': 'no face in frame'})
    r = TP.arm(source='camera')
    assert r['ok'] is False and r['refused'] is True
    assert 'DEAD-001' in r['rules']
    assert not isolated.exists(), 'a refused arm must not write a presence record'


def test_camera_arm_with_a_face_records_it(isolated, monkeypatch):
    monkeypatch.setattr(TP, 'sense', lambda *a, **k: {'present': True, 'faces': 1})
    r = TP.arm(source='camera', ttl=5)
    assert r['ok'] is True
    rec = json.loads(isolated.read_text(encoding='utf-8'))
    assert rec['source'] == 'camera' and rec['faces'] == 1


def test_sensing_is_zero_ml():
    """No model weights, no tokens, no network in the sensing path."""
    src = Path(TP.__file__).read_text(encoding='utf-8')
    body = src[src.index('def sense('):src.index('def arm(')]
    for bad in ('torch', 'onnx', 'mediapipe', 'urlopen', 'requests.', 'api_key'):
        assert bad not in body, f'sensing must stay zero-ML: found {bad!r}'
