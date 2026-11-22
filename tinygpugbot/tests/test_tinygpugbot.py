"""tinyGPUBOT tests — the actor instrument.

Every test pins a REFUSAL or a MEASUREMENT. A bot that cannot refuse an
unscriptable cue is not a governed actor.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tinygpugbot as tg  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]      # C:/æ


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    led = tmp_path / 'tinygpugbot.jsonl'
    monkeypatch.setattr(tg, 'LEDGER', led)
    return led


def write_script(tmp_path, **over):
    s = {'schema': 'actor/script/1', 'title': 'T',
         'cast': [{'id': 'asimov', 'model': 'm',
                   'traces': {'walk': str(ROOT / 'verbs' / 'out' / 'walk.json')}}],
         'cues': [{'t': 0.0, 'actor': 'asimov', 'verb': 'walk', 'line': 'x',
                   'camera': {'az': 1.5}},
                  {'t': 3.0, 'actor': 'asimov', 'verb': 'walk', 'line': 'y'}],
         'seconds': 6.0, 'voice': {'voice': 'hermes', 'seed': 1},
         'output': {'name': 't', 'workdir': str(tmp_path)}}
    s.update(over)
    p = tmp_path / 's.json'
    p.write_text(json.dumps(s), encoding='utf-8')
    return p


def test_doctor_measures_the_pipeline():
    d = tg.doctor()
    assert d['ok'] and d['missing'] == []
    assert d['checks']['renderer'] and d['checks']['cuda'] is True


def test_cast_resolves_a_valid_script(tmp_path):
    c = tg.cast(write_script(tmp_path))
    assert c['ok'] and not c['refused'] and len(c['resolved']) == 2
    assert c['resolved'][0]['trace_sha256']
    assert c['ledger']


def test_cast_refuses_unknown_actor(tmp_path):
    c = tg.cast(write_script(tmp_path, cues=[{'t': 0, 'actor': 'ghost', 'verb': 'walk'}]))
    assert not c['ok'] and c['refused']
    assert any('unknown actor' in r for r in c['refusals'])


def test_cast_refuses_unknown_verb(tmp_path):
    c = tg.cast(write_script(tmp_path, cues=[{'t': 0, 'actor': 'asimov', 'verb': 'teleport'}]))
    assert not c['ok'] and any('no trace for teleport' in r for r in c['refusals'])


def test_cast_refuses_a_missing_trace(tmp_path):
    s = write_script(tmp_path)
    d = json.loads(s.read_text(encoding='utf-8'))
    d['cast'][0]['traces']['walk'] = str(tmp_path / 'nope.json')
    s.write_text(json.dumps(d), encoding='utf-8')
    c = tg.cast(s)
    assert not c['ok'] and any('trace missing' in r for r in c['refusals'])


def test_cast_refuses_a_wrong_schema(tmp_path):
    c = tg.cast(write_script(tmp_path, schema='actor/script/9'))
    assert not c['ok'] and 'schema' in c['reason']


def test_cast_refuses_a_missing_script(tmp_path):
    c = tg.cast(tmp_path / 'absent.json')
    assert not c['ok'] and 'no such script' in c['reason']


def test_perform_dry_does_not_render(tmp_path):
    r = tg.perform(write_script(tmp_path), dry=True)
    assert r['ok'] and r['proof_spec']
    assert r['ledger']


def test_ledger_is_a_chain_and_detects_tamper(isolated_ledger):
    tg.receipt('a', {'x': 1}); tg.receipt('b', {'x': 2})
    lg = tg.ledger()
    assert lg['ok'] and lg['length'] == 2
    lines = isolated_ledger.read_text(encoding='utf-8').splitlines()
    rec = json.loads(lines[0]); rec['action'] = 'tampered'
    isolated_ledger.write_text('\n'.join([json.dumps(rec, ensure_ascii=False,
                                                     sort_keys=True)] + lines[1:]) + '\n',
                               encoding='utf-8')
    assert not tg.ledger()['ok']
