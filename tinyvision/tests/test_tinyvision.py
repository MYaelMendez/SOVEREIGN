"""tinyVISION tests — supervision pointed at the policy.

The pipeline: a policy trace becomes a film of the real CAD; the film is
supervised and tracked; the visual trajectory is compared with the physics.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tinyvision as tv  # noqa: E402

HERE = Path(__file__).resolve().parent
FILM = HERE.parent / 'out' / 'policy-vision.mp4'
TRACE = HERE.parent.parent / 'policies' / '0818' / 'trace.json'


def need(p):
    if not Path(p).exists():
        pytest.skip(f'{p} not built yet')
    return Path(p)


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    led = tmp_path / 'tinyvision.jsonl'
    monkeypatch.setattr(tv, 'LEDGER', led)
    return led


def test_doctor_reports_engine_and_renderer():
    d = tv.doctor()
    assert d['ok']
    assert d['engine'] == 'supervisionvidaeo.vision'
    assert d['renderer'].endswith('rtx_asimov.py')


def test_supervise_reads_the_gate_from_the_film():
    r = tv.supervise(need(FILM))
    assert r['calidad'] == 'PASS'
    assert r['frames_negros'] == 0
    assert r['luminancia_media'] > 20.0
    assert r['movimiento_medio'] > 0.5


def test_track_isolates_one_blob_not_the_whole_frame():
    r = tv.track(need(FILM))
    assert r['ok'] and r['tracks'] == 1
    assert r['points'] > 200
    assert abs(r['displacement_px']['dx']) > 1.0


def test_agree_compares_both_units():
    r = tv.agree(need(TRACE), need(FILM))
    assert r['ok'] and r['coherent'] and r['direction_ok']
    assert r['physics']['success'] is True
    assert r['visual']['tracks'] == 1
    assert 'different units' in r['note']


def test_missing_film_is_a_refusal(tmp_path):
    r = tv.supervise(tmp_path / 'nope.mp4')
    assert not r['ok'] and r['refused']


def test_ledger_is_a_hash_chain():
    tv.supervise(need(FILM))
    lg = tv.ledger()
    assert lg['ok'] and lg['length'] == 1


def test_ledger_detects_tamper(isolated_ledger):
    tv.receipt('x', {'a': 1})
    raw = isolated_ledger.read_text(encoding='utf-8').splitlines()
    rec = json.loads(raw[0]); rec['action'] = 'y'
    isolated_ledger.write_text(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n',
                               encoding='utf-8')
    assert not tv.ledger()['ok']
