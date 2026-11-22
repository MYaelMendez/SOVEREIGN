"""Autopilot dispatch tests — a plan is never authority; risk is derived from bytes."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import pytest

MOD = Path(__file__).resolve().parent / 'autopilot_dispatch.py'
spec = importlib.util.spec_from_file_location('autopilot_dispatch', MOD)
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(d, 'LEDGER', tmp_path / 'dispatch.jsonl')


def plan(*steps):
    return {'summary': 'test plan', 'steps': list(steps)}


LOCAL = {'tool': 'vscoder_observe', 'params': {}, 'reason': 'inspect'}
DURABLE = {'tool': 'vscoder_build', 'params': {}, 'reason': 'build'}


def test_status_reports_both_halves():
    s = d.status()
    assert s['ok'] and s['planner_exists'] and s['healer_exists']
    assert 'vscoder_observe' in s['read_only'] and 'vscoder_build' in s['durable']


def test_plan_schema_refused():
    ok, why = d.validate_plan({'steps': []})
    assert not ok
    r = d.run(plan())
    assert r['refused'] and r['decision'] == 'REFUSE'


def test_unsupported_tool_refused():
    r = d.run(plan({'tool': 'terminal.run', 'params': {}, 'reason': 'x'}))
    assert r['refused'] and 'REFUSE' == r['decision']


def test_risk_label_contradiction_refused():
    r = d.run(plan({'tool': 'vscoder_observe', 'risk': 'DURABLE', 'params': {}}))
    assert r['refused'], 'a forged DURABLE label on a read-only tool must be refused'


def test_dry_run_requires_approval_for_durable():
    r = d.run(plan(LOCAL, DURABLE), dry=True)
    assert r['decision'] == 'REQUIRE_APPROVAL' and not r['granted']
    assert r['results'][0]['decision'] == 'DRY_RUN'
    assert r['results'][1]['decision'] == 'REQUIRE_APPROVAL'


def test_grant_never_self_grants():
    g = d.grant(plan(LOCAL, DURABLE))
    assert not g['ok'] and g['grants'] is False and g['required']['approval']['human']


def test_bound_grant_allows_durable_dry_run():
    p = plan(LOCAL, DURABLE)
    act = d.sha(d.canon({'plan': p}))
    r = d.run(p, {'approval': {'human': True, 'action_sha256': act}}, dry=True)
    assert r['granted'] and r['decision'] == 'DRY_RUN'
    assert r['results'][1]['granted'] is True


def test_wrong_grant_still_requires_approval():
    p = plan(DURABLE)
    r = d.run(p, {'approval': {'human': True, 'action_sha256': 'wrong'}}, dry=True)
    assert not r['granted'] and r['decision'] == 'REQUIRE_APPROVAL'


def test_dispatch_never_executes_shell_or_edits():
    r = d.run(plan(LOCAL, DURABLE), dry=False)  # no grant
    assert all(x['decision'] in ('LOCAL_PROBE', 'REQUIRE_APPROVAL') for x in r['results'])
    assert 'never executes' in r['note']


def test_ledger_chain_and_tamper():
    d.run(plan(LOCAL))
    d.run(plan(DURABLE))
    lg = d.ledger()
    assert lg['ok'] and lg['length'] == 2
    lines = d.LEDGER.read_text(encoding='utf-8').splitlines()
    first = json.loads(lines[0]); first['decision'] = 'APPLY'
    d.LEDGER.write_text('\n'.join([json.dumps(first, ensure_ascii=False)] + lines[1:]) + '\n',
                        encoding='utf-8')
    assert not d.ledger()['ok']
