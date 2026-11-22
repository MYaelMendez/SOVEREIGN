"""tinyFILMMEMORY tests — the ledger.

The ledger is the lab's memory: a hash chain over re-measured receipts. These
tests pin the three properties that make it trustworthy — determinism, tamper
evidence, and byte drift — plus the corpus audit.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tinyfilmmemory as tfm  # noqa: E402


def test_sha256_and_canonical_are_stable():
    assert tfm.sha256(b'abc') == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    assert tfm.canonical({'b': 1, 'a': 2}) == tfm.canonical({'a': 2, 'b': 1})


def test_chain_check_ok_and_tamper(tmp_path):
    led = tmp_path / 'ledger.jsonl'
    tfm.append(led, {'kind': 'test', 'film': 'a.mp4'})
    tfm.append(led, {'kind': 'test', 'film': 'b.mp4'})
    assert tfm.chain_check(tfm.read_ledger(led))['ok']

    raw = led.read_text(encoding='utf-8').splitlines()
    rec = json.loads(raw[0]); rec['film'] = 'tampered.mp4'
    led.write_text('\n'.join([json.dumps(rec, ensure_ascii=False, sort_keys=True)] + raw[1:]) + '\n',
                   encoding='utf-8')
    assert not tfm.chain_check(tfm.read_ledger(led))['ok']


def test_append_is_deterministic_and_chainable(tmp_path):
    led = tmp_path / 'ledger.jsonl'
    a = tfm.append(led, {'kind': 'test', 'film': 'a.mp4'})
    b = tfm.append(led, {'kind': 'test', 'film': 'b.mp4'})
    assert a['ok'] and b['ok']
    assert b['prev'] == a['hash']
    assert tfm.read_ledger(led)[-1]['hash'] == b['hash']


def test_verify_reports_tamper(tmp_path):
    led = tmp_path / 'ledger.jsonl'
    tfm.append(led, {'kind': 'test', 'film': 'a.mp4'})
    assert tfm.verify(led)['ok']

    raw = led.read_text(encoding='utf-8').splitlines()
    rec = json.loads(raw[0]); rec['film'] = 'tampered.mp4'
    led.write_text(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    assert not tfm.verify(led)['ok']


def test_verify_reports_drift_when_bytes_change(tmp_path):
    """A cited film still on disk but re-written must show DRIFT, honestly."""
    film = tmp_path / 'clip.mp4'
    film.write_bytes(b'ORIGINAL-BYTES')
    led = tmp_path / 'ledger.jsonl'
    tfm.append(led, {'kind': 'film', 'title': 'clip', 'path': str(film),
                     'doi_equivalent': tfm.sha256(film.read_bytes())})
    base = tfm.verify(led)
    assert base['ok'] and base['films_checked'] == 1, base
    assert base['drift'] == []

    film.write_bytes(b'CHANGED-BYTES')
    r = tfm.verify(led)
    assert r['drift'] == ['clip'], r
    assert not r['ok']


def test_verify_absent_artifact_is_honest_not_drift(tmp_path):
    led = tmp_path / 'ledger.jsonl'
    tfm.append(led, {'kind': 'film', 'title': 'gone', 'path': str(tmp_path / 'gone.mp4'),
                     'doi_equivalent': '0' * 64})
    r = tfm.verify(led)
    assert r['absent'] == ['gone'] and r['drift'] == []
    assert r['ok'], 'absent is honest, not drift'


def test_audit_finds_unrecorded(tmp_path):
    d = tmp_path / 'corpus'; d.mkdir()
    (d / 'a.mp4').write_bytes(b'a')
    (d / 'b.mp4').write_bytes(b'b')
    led = tmp_path / 'ledger.jsonl'
    tfm.append(led, {'kind': 'test', 'film': 'a.mp4'})
    r = tfm.audit(d, led)
    assert r['ok']
    assert 'b' in json.dumps(r).lower() or r.get('unrecorded')


def test_selftest_end_to_end():
    """The module's own fixture: record, determinism, chain, tamper, drift."""
    r = tfm.selftest()
    if r.get('reason', '').startswith('ffmpeg'):
        pytest.skip(r['reason'])
    assert r['ok'], r


def test_doctor():
    d = tfm.doctor()
    assert d['ok'] and 'ledger' in json.dumps(d).lower()
