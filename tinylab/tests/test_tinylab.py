"""tinyLAB tests — the laboratory grading itself.

The recursion is the point: a study produces a receipt, and the receipt's
`change` becomes the next brief. These tests pin that loop, the inventory, and
the ledger — not the slow full-suite run.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tinylab as tl  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    led = tmp_path / 'tinylab.jsonl'
    monkeypatch.setattr(tl, 'LEDGER', led)
    return led


def test_inventory_finds_the_family():
    ins = tl.instruments()
    names = {i['name'] for i in ins}
    assert {'tinycuda', 'tinypython', 'tinyonnx', 'tinyvision', 'tinylab'} <= names
    assert any(i['cases'] > 0 for i in ins)


def test_doctor_reports_what_is_untested():
    d = tl.doctor()
    assert d['ok'] and d['family'] >= 12
    assert isinstance(d['untested'], list)
    assert d['present'] >= 10


def test_next_brief_refuses_before_any_study():
    r = tl.next_brief()
    assert not r['ok'] and 'no study' in r['reason']


def test_the_recursion_receipt_becomes_the_next_brief(isolated_ledger):
    tl.receipt('study', {'change': ['give tinyX a refusal-pinned suite'],
                         'untested': ['tinyX']})
    b = tl.next_brief()
    assert b['ok'] and b['brief'] == ['give tinyX a refusal-pinned suite']
    assert b['note'] == 'the lab instructed itself'


def test_study_receipt_carries_prev_change(isolated_ledger):
    tl.receipt('study', {'change': ['first instruction'], 'untested': []})
    tl.receipt('study', {'change': ['second instruction'], 'untested': [],
                         'prev_change': ['first instruction']})
    b = tl.next_brief()
    assert b['brief'] == ['second instruction']


def test_no_finding_is_not_an_instruction(monkeypatch):
    """An all-green study must emit a non-actionable sentinel, never a task."""
    monkeypatch.setattr(tl, 'instruments', lambda: [
        {'name': 'tinyX', 'module': True, 'cases': 5}])
    monkeypatch.setattr(tl, 'doctor', lambda: {
        'ok': True, 'present': 1, 'family': 1, 'untested': []})
    monkeypatch.setattr(tl, 'selftest', lambda: {'ok': True, 'passed': 1, 'total': 1})
    r = tl.study()
    assert r['ok'] and r['actionable'] is False
    assert r['change'] == ['NO FINDING · all suites green, no refusal unpinned']
    assert 'checkpoint' not in ' '.join(r['change'])
    # the sentinel must survive into the brief, marked non-actionable
    b = tl.next_brief()
    assert b['actionable'] is False
    assert b['brief'] == r['change']


def test_next_brief_defaults_old_receipts_to_actionable(isolated_ledger):
    """Receipts written before this field existed stay actionable."""
    tl.receipt('study', {'change': ['legacy instruction'], 'untested': []})
    b = tl.next_brief()
    assert b['actionable'] is True
    assert b['brief'] == ['legacy instruction']


def test_legacy_hardcoded_fallback_is_not_promoted(isolated_ledger):
    """The old default-branch string must not become an instruction retroactively."""
    tl.receipt('study', {'change': ['close the loop back into the policy: '
                                    'let the visual grade select or reject a checkpoint'],
                         'untested': []})
    b = tl.next_brief()
    assert b['actionable'] is False


def test_ledger_chain_and_tamper(isolated_ledger):
    tl.receipt('a', {'x': 1})
    tl.receipt('b', {'x': 2})
    lg = tl.ledger()
    assert lg['ok'] and lg['length'] == 2
    lines = isolated_ledger.read_text(encoding='utf-8').splitlines()
    rec = json.loads(lines[0]); rec['action'] = 'tampered'
    isolated_ledger.write_text('\n'.join([json.dumps(rec, ensure_ascii=False,
                                                     sort_keys=True)] + lines[1:]) + '\n',
                               encoding='utf-8')
    assert not tl.ledger()['ok']
