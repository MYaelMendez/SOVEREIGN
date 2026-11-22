"""Visual checkpoint gate tests — pin the REFUSALS, not just the happy path."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parent / 'visual_checkpoint_gate.py'
spec = importlib.util.spec_from_file_location('visual_checkpoint_gate', MOD)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

CKPT = {'id': 'film-916', 'artifact': 'film.mp4', 'sha256': 'deadbeef', 'bytes': 123}
GOOD = {'luminance': 34.7, 'contrast': 38.49, 'motion': 3.383,
        'black_pct': 0.0, 'mux_delta_s': 0.0}
BAD = {'luminance': 5.0, 'contrast': 2.0, 'motion': 0.0,
       'black_pct': 0.5, 'mux_delta_s': 2.0}


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(g, 'LEDGER', tmp_path / 'gate.jsonl')


def grant_for(ckpt):
    return {'approval': {'human': True,
                         'action_sha256': g.checkpoint_sha(ckpt),
                         'checkpoint_id': ckpt['id']}}


def test_doctor_measures_does_not_assert():
    d = g.doctor()
    assert d['ok'] and 'thresholds' in d
    assert 'refuse' in d['rule'] and 'human grant' in d['rule']


def test_grade_fails_closed_on_missing_measurement():
    r = g.grade(CKPT, {'luminance': 30})  # other fields absent
    assert r['verdict'] == 'REFUSE' and len(r['reasons']) >= 3
    assert r['authority'] == 'none — evidence only'


def test_bad_grade_refuses_even_with_a_valid_grant():
    r = g.gate(CKPT, BAD, grant_for(CKPT))
    assert r['refused'] and r['decision'] == 'REFUSE' and not r['granted']


def test_passing_grade_alone_requires_approval():
    r = g.gate(CKPT, GOOD)
    assert r['refused'] and r['decision'] == 'REQUIRE_APPROVAL'
    assert not r['granted'] and 'human' in str(r['required'])


def test_grant_never_self_grants():
    r = g.grant(CKPT)
    assert not r['ok'] and r['grants'] is False
    assert r['required']['approval']['human'] is True


def test_wrong_checkpoint_grant_is_refused_replay():
    other = dict(CKPT, id='other', sha256='otherhash')
    r = g.gate(CKPT, GOOD, grant_for(other))
    assert r['refused'] and r['decision'] == 'REQUIRE_APPROVAL'


def test_non_human_approval_is_refused():
    ap = grant_for(CKPT)
    ap['approval']['human'] = False
    r = g.gate(CKPT, GOOD, ap)
    assert r['refused'] and r['decision'] == 'REQUIRE_APPROVAL'


def test_valid_grant_accepts():
    r = g.gate(CKPT, GOOD, grant_for(CKPT))
    assert r['ok'] and r['decision'] == 'ACCEPT' and r['granted']


def test_ledger_chain_records_decisions_and_detects_tamper():
    g.gate(CKPT, BAD, grant_for(CKPT))          # REFUSE
    g.gate(CKPT, GOOD)                          # REQUIRE_APPROVAL
    g.gate(CKPT, GOOD, grant_for(CKPT))         # ACCEPT
    lg = g.ledger()
    assert lg['ok'] and lg['length'] == 3
    lines = g.LEDGER.read_text(encoding='utf-8').splitlines()
    first = json.loads(lines[0]); first['decision'] = 'ACCEPT'  # tamper
    g.LEDGER.write_text('\n'.join([json.dumps(first, ensure_ascii=False)] + lines[1:]) + '\n',
                        encoding='utf-8')
    assert not g.ledger()['ok']


def test_contract_read_from_artifact_not_name():
    a = g.checkpoint_sha({'id': 'x', 'sha256': 'one'})
    b = g.checkpoint_sha({'id': 'x', 'sha256': 'two'})
    assert a != b
