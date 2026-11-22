"""tinyPOLICY tests — command and control, not motion.

Every test pins a REFUSAL or a MEASUREMENT. None of them moves anything: the
domain is a simulation, and the gate's refusals are the contract.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tinypolicy as tpol  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    led = tmp_path / 'tinypolicy.jsonl'
    monkeypatch.setattr(tpol, 'LEDGER', led)
    return led


def test_doctor_reports_the_domain():
    d = tpol.doctor()
    assert d['domain'] == 'mobility.foundation'
    assert d['schema'] == 'mobility.foundation/c2/1'
    assert d['deps'].startswith('tinypython')


def test_verb_surface_is_finite_and_named():
    v = tpol.verbs()
    assert v['ok'] and v['count'] == len(v['verbs'])
    assert {'plan', 'trace', 'gate', 'stand', 'walk'} <= set(v['verbs'])
    motion = [k for k, x in v['verbs'].items() if x['class'] == 'motion']
    assert motion and all('signature' in v['verbs'][k]['needs'] for k in motion)


def test_plan_never_grants_or_connects():
    r = tpol.plan('walk', vx=0.4)
    assert r['ok'] and r['executed'] is False and r['grants'] is False
    assert r['plan']['connects'] is False
    assert r['receipt']


def test_unknown_verb_is_a_refusal():
    r = tpol.plan('teleport')
    assert not r['ok'] and r['refused'] and r['grants'] is False


def test_simulation_is_allowed_but_never_executes():
    r = tpol.exec('trace')
    assert r['ok'] and r['executed'] is False and r['grants'] is False
    assert 'picture of a plan' in r['note']


def test_motion_is_refused_without_presence_and_signature():
    r = tpol.exec('stand')
    assert not r['ok'] and r['refused'] and r['grants'] is False
    assert r['executed'] is False
    assert 'ACT-001' in r['rules'] and 'signature' in str(r['reason'])


def test_gate_simulation_intent_is_allowed():
    g = tpol.gate('simulate')
    assert g['ok'] and g['decision'] == 'allow' and g['grants'] is False


def test_gate_motion_intent_is_refused_when_no_presence():
    g = tpol.gate('move')
    assert g['decision'] == 'require_approval'
    assert 'DEAD-001' in g['rules']


def test_ledger_is_a_hash_chain():
    tpol.plan('walk')
    tpol.gate('move')
    lg = tpol.ledger()
    assert lg['ok'] and lg['length'] == 2
    lines = tpol._read()
    assert lines[1]['prev'] == lines[0]['hash']


def test_ledger_detects_tamper(isolated_ledger):
    tpol.plan('walk')
    raw = isolated_ledger.read_text(encoding='utf-8').splitlines()
    rec = json.loads(raw[0]); rec['action'] = 'exec'
    isolated_ledger.write_text(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n',
                               encoding='utf-8')
    lg = tpol.ledger()
    assert not lg['ok'] and lg['broken_at'] == 1


def test_status_is_read_only_and_honest():
    s = tpol.status()
    assert s['ok'] and s['domain'] == 'mobility.foundation'
    assert s['ledger']['ok']
    assert 'no hardware' in s['note']
