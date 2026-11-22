"""Healer tests — Playwright-Healer discipline: refusals, skip, grant, no auto-merge."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parent / 'healer.py'
spec = importlib.util.spec_from_file_location('healer', MOD)
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(h, 'LEDGER', tmp_path / 'healer.jsonl')


def test_unknown_signature_refuses_no_invention():
    r = h.heal('invent_a_fix', 'C:/æ/whatever.py')
    assert r['refused'] and r['decision'] == 'REFUSE'
    assert 'refusing to invent' in r['reason']
    assert 'verdict_separator_emdash' in r['known']


def test_missing_artifact_fails_closed():
    r = h.heal('verdict_separator_emdash', 'C:/æ/does_not_exist.py')
    assert r['refused'] and 'no pass claimed' in r['reason']


def test_strategies_are_bounded_and_named():
    s = h.strategies()
    assert s['ok'] and s['max_turns'] > 0
    assert 'tinylab_fallback_instruction' in s['signatures']


def test_signature_absent_skips_without_touching_artifact(tmp_path):
    p = tmp_path / 'clean.py'
    original = "# clean source with no defect\nVERDICT = re.compile(r'[-–—]')\n"
    p.write_text(original, encoding='utf-8')
    r = h.heal('verdict_separator_emdash', str(p))
    assert r['decision'] == 'SKIP' and not r['refused']
    assert p.read_text(encoding='utf-8') == original  # never wrote the real file


def test_grant_never_self_grants():
    r = h.grant('verdict_separator_emdash', 'C:/æ/x.py')
    assert not r['ok'] and r['grants'] is False
    assert r['required']['approval']['human'] is True


def test_promote_requires_bound_grant():
    r = h.promote('deadbeef', 'C:/æ/x.py')
    assert r['refused'] and r['decision'] == 'REQUIRE_APPROVAL'
    assert not r['granted']


def test_wrong_grant_refused():
    ap = {'approval': {'human': True, 'action_sha256': 'wrong', 'target': 'C:/æ/x.py'}}
    r = h.promote('deadbeef', 'C:/æ/x.py', ap)
    assert r['refused'] and r['decision'] == 'REQUIRE_APPROVAL'


def test_ledger_chain_and_tamper():
    h.heal('unknown', 'x')
    h.heal('verdict_separator_emdash', 'missing')
    lg = h.ledger()
    assert lg['ok'] and lg['length'] == 2
    lines = h.LEDGER.read_text(encoding='utf-8').splitlines()
    first = json.loads(lines[0]); first['decision'] = 'APPLY'
    h.LEDGER.write_text('\n'.join([json.dumps(first, ensure_ascii=False)] + lines[1:]) + '\n',
                        encoding='utf-8')
    assert not h.ledger()['ok']


def test_repair_is_deterministic_on_artifact():
    src = "VERDICT = re.compile(r'\\*\\*(proved|broke|change)\\*\\*\\s*[-–]\\s*')"
    st = h.STRATEGIES['verdict_separator_emdash']
    assert st['detect'](src)
    out = st['repair'](src)
    assert '—' in out and '[-–—]' in out
    assert st['repair'](st['repair'](src)) == out  # idempotent, no runaway


def test_gate_is_bound_to_staged_bytes_not_a_different_artifact(tmp_path):
    """A receipt from another artifact must never license this patch."""
    p = tmp_path / 'target.py'
    p.write_text("VERDICT = re.compile(r'[-–]')\n", encoding='utf-8')
    stage = str(p) + '.healer-stage'
    monkeypatch_stage = stage
    import os
    old = os.environ.get('HEALER_STAGE')
    os.environ['HEALER_STAGE'] = monkeypatch_stage
    try:
        r = h.heal('verdict_separator_emdash', str(p))
        assert r['decision'] == 'PROPOSE' and r['gate_scope'] == 'staged_bytes'
        assert '[-–—]' in Path(stage).read_text(encoding='utf-8')
        # the staged bytes carried the fix; the real artifact was never written
        assert '[-–]' in p.read_text(encoding='utf-8')
        # a check on a DIFFERENT artifact cannot license this proposal
        assert r['diff_sha256'] == h.sha(r['diff'].encode())
    finally:
        if old is None:
            os.environ.pop('HEALER_STAGE', None)
        else:
            os.environ['HEALER_STAGE'] = old
