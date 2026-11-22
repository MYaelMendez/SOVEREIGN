"""Governed self-repair tests — the loop terminates at a human gate, never APPLY."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import pytest

MOD = Path(__file__).resolve().parent / 'governed_self_repair.py'
spec = importlib.util.spec_from_file_location('gsr', MOD)
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(g, 'LEDGER', tmp_path / 'repair.jsonl')


def test_status_names_all_four_links_and_never_apply():
    s = g.status()
    assert s['ok'] and all(s['links'].values())
    assert 'APPLY' in s['never'] and 'REQUIRE_APPROVAL' in s['terminal_states']


def test_no_finding_stops_without_inventing_work():
    b = {'ok': True, 'actionable': False, 'brief': ['NO FINDING']}
    r = g.cycle('C:/æ/does_not_matter.py', 'anything', brief=b)
    assert r['decision'] == 'STOP' and r['granted'] is False
    assert 'not an instruction' in r['reason']


def test_no_brief_stops():
    r = g.cycle('x', 'y', brief={'ok': False, 'reason': 'none'})
    assert r['decision'] == 'STOP'


def test_actionable_brief_ends_at_require_approval(tmp_path, monkeypatch):
    target = tmp_path / 'broken.py'
    target.write_text("VERDICT = re.compile(r'[-–]')\n", encoding='utf-8')
    stage = str(target) + '.healer-stage'
    import os
    old = os.environ.get('HEALER_STAGE')
    os.environ['HEALER_STAGE'] = stage
    try:
        b = {'ok': True, 'actionable': True, 'brief': ['repair verdict separator']}
        r = g.cycle(str(target), 'verdict_separator_emdash', brief=b)
        assert r['decision'] == 'REQUIRE_APPROVAL' and not r['granted']
        assert r['plan_hash'] and r['heal_hash'] and r['gate_hash']
        assert r['receipt'] and r['next']
        # the real artifact was never written
        assert '[-–]' in target.read_text(encoding='utf-8')
    finally:
        if old is None:
            os.environ.pop('HEALER_STAGE', None)
        else:
            os.environ['HEALER_STAGE'] = old


def test_one_receipt_binds_three_hashes(tmp_path):
    target = tmp_path / 'broken.py'
    target.write_text("VERDICT = re.compile(r'[-–]')\n", encoding='utf-8')
    import os
    old = os.environ.get('HEALER_STAGE')
    os.environ['HEALER_STAGE'] = str(target) + '.healer-stage'
    try:
        b = {'ok': True, 'actionable': True, 'brief': ['fix']}
        r = g.cycle(str(target), 'verdict_separator_emdash', brief=b)
        recs = json.loads(g.LEDGER.read_text(encoding='utf-8').splitlines()[-1])
        assert recs['plan_hash'] == r['plan_hash']
        assert recs['heal_hash'] == r['heal_hash']
        assert recs['gate_hash'] == r['gate_hash']
        assert recs['decision'] == 'REQUIRE_APPROVAL'
    finally:
        if old is None:
            os.environ.pop('HEALER_STAGE', None)
        else:
            os.environ['HEALER_STAGE'] = old


def test_ledger_chain_and_tamper():
    g.cycle('x', 'y', brief={'ok': True, 'actionable': False})
    g.cycle('x', 'y', brief={'ok': False})
    assert g.ledger()['ok'] and g.ledger()['length'] == 2
    lines = g.LEDGER.read_text(encoding='utf-8').splitlines()
    first = json.loads(lines[0]); first['decision'] = 'APPLY'
    g.LEDGER.write_text('\n'.join([json.dumps(first, ensure_ascii=False)] + lines[1:]) + '\n',
                        encoding='utf-8')
    assert not g.ledger()['ok']
