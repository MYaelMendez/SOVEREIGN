"""tinyPLUGIN tests — the static oracle for silent failures.

Every defect in this oracle produces a GREEN signal at install: the pane appears,
`validate` passes, then one tab is dead or every tool raises. The tests pin the
detections on fixtures, because that is the whole point of the oracle.
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tinyplugin as tp  # noqa: E402


@pytest.fixture
def plugin_tree(tmp_path, monkeypatch):
    (tmp_path / 'plugin.js').write_text('// fixture\n')
    monkeypatch.setattr(tp, '_trees', lambda pid: (tmp_path, tmp_path))
    return tmp_path


def codes(res):
    return {f['code'] for f in res['findings']}


def test_undefined_capital_constant(plugin_tree):
    (plugin_tree / 'plugin.js').write_text(
        'export function register() { return SOME_UNDEFINED_CONSTANT; }\n')
    r = tp.grade('fixture')
    assert 'JS_UNDEFINED_CONST' in codes(r)
    assert r['errors'] >= 1


def test_invented_host_method(plugin_tree):
    (plugin_tree / 'plugin.js').write_text(
        'export function register(ctx) { ctx.host.thisMethodDoesNotExist(); }\n')
    r = tp.grade('fixture')
    assert 'JS_INVENTED_HOST' in codes(r)


def test_vlc_pl_add_is_flagged(plugin_tree):
    (plugin_tree / 'plugin.js').write_text(
        'export function register(ctx) { ctx.vlc.pl_add("x"); }\n')
    r = tp.grade('fixture')
    assert 'VLC_PL_ADD' in codes(r)


def test_clean_plugin_has_no_error_findings(plugin_tree):
    (plugin_tree / 'plugin.js').write_text(
        'const X = 1;\nexport function register(ctx) { return X; }\n')
    r = tp.grade('fixture')
    errs = [f for f in r['findings'] if f['severity'] == 'error']
    assert errs == []


def test_missing_plugin_is_a_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, '_trees', lambda pid: (tmp_path / 'nope', tmp_path / 'nope'))
    r = tp.grade('absent')
    assert not r['ok'] and r['reward'] == 0.0


def test_doctor_and_audit_run():
    d = tp.doctor()
    assert d['ok']
    a = tp.audit()
    assert 'plugins' in a or a.get('ok') is not False
