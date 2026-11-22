"""tinyONNX tests — the policy oracle.

The finding these pin: of the five Menlo policies, only two match the viewer's
78-in / 23-out contract. The other three are 12-action partial-body policies and
must be REFUSED, not coerced into the full-body harness.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tinyonnx as ton  # noqa: E402

POL = Path(__file__).resolve().parent.parent.parent / 'policies'


def pol(name):
    return POL / name / 'policy' / 'policy.onnx'


def need(name):
    p = pol(name)
    if not p.exists():
        pytest.skip(f'{name} not pulled yet')
    return p


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    led = tmp_path / 'tinyonnx.jsonl'
    monkeypatch.setattr(ton, 'LEDGER', led)
    return led


def test_doctor_reports_the_contract_and_the_set():
    d = ton.doctor()
    assert d['ok']
    assert d['viewer_contract'] == {'in': 78, 'out': 23}
    assert d['count'] >= 1
    assert any(p['contract_ok'] for p in d['policies'])


def test_inspect_reads_the_baseline_contract():
    r = ton.inspect(need('0818'))
    assert r['ok'] and r['inputs'][0]['shape'] == [1, 78]
    assert r['outputs'][0]['shape'] == [1, 23]
    assert r['provider'] == 'CPUExecutionProvider'
    assert r['sha256'].startswith('47f70691')


def test_contract_accepts_the_baseline():
    c = ton.contract(need('0818'))
    assert c['ok'] and not c['refused']
    assert c['actual'] == {'in': 78, 'out': 23}


def test_contract_refuses_a_partial_body_policy():
    c = ton.contract(need('26-10-05-upper-body'))
    assert not c['ok'] and c['refused']
    assert c['actual'] == {'in': 78, 'out': 12}
    assert 'contract mismatch' in c['reason']


def test_blind_policy_has_a_narrower_observation():
    c = ton.contract(need('26-10-17-upper-body-blind'))
    assert not c['ok'] and c['actual'] == {'in': 45, 'out': 12}


def test_run_refuses_a_policy_that_does_not_match():
    r = ton.run(POL / '26-10-05-upper-body')
    assert not r['ok'] and r['refused'] and r['grants'] is False
    assert 'contract mismatch' in r['reason']


def test_run_the_baseline_and_grade_it():
    r = ton.run(POL / '0818', vx=0.4, duration=6.0)
    assert r['ok'] and r['policy_sha256'].startswith('47f70691')
    assert r['grants'] is False and r['executed'] is False
    g = ton.grade(r['trace'])
    assert g['ok'] and g['obeyed_command'] and not g['fell']
    assert g['travel_x_m'] > 0.0


def test_ledger_is_a_hash_chain():
    ton.run(POL / '0818', vx=0.4, duration=3.0)
    lg = ton.ledger()
    assert lg['ok'] and lg['length'] == 1
    lines = ton._read()
    assert lines[0]['prev'] == '0' * 64


def test_ledger_detects_tamper(isolated_ledger):
    ton.receipt('x', {'a': 1})
    raw = isolated_ledger.read_text(encoding='utf-8').splitlines()
    rec = json.loads(raw[0]); rec['action'] = 'y'
    isolated_ledger.write_text(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n',
                               encoding='utf-8')
    assert not ton.ledger()['ok']


def test_compare_the_two_full_body_policies():
    r = ton.compare(POL / '0818', POL / '26-09-24', vx=0.4, duration=6.0)
    assert r['ok'] and r['winner'] in ('a', 'b', 'tie')
    assert r['a']['travel_x_m'] is not None and r['b']['travel_x_m'] is not None
    assert 'same command' in r['note']
