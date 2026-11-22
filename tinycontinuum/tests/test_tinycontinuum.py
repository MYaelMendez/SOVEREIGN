"""tinyCONTINUUM tests — the TIME axis.

Both studio defects found on 2026-11-20 were ordering defects: a frozen tail and
a stale-frame reversal. Neither is a property of any single frame, so a pixel
gate passes them. These tests pin the order properties the oracle claims.
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tinycontinuum as tc  # noqa: E402


def timeline(n=8, dt=1.0, v0=0):
    return [{'t': i * dt, 'v': v0 + i} for i in range(n)]


def codes(res):
    return {d['code'] for d in res['defects']}


def test_clean_timeline_passes():
    r = tc.grade_timeline(timeline(), span=(0.0, 7.0))
    assert r['ok'] and r['reward'] == 1.0 and r['defects'] == []
    assert r['samples'] == 8


def test_too_few_samples_is_a_refusal():
    r = tc.grade_timeline([{'t': 0, 'v': 1}])
    assert not r['ok'] and r['reward'] == 0.0
    assert 'TOO_FEW' in codes(r)


def test_freeze_is_detected():
    samples = timeline()
    for s in samples[3:6]:
        s['v'] = samples[2]['v']          # value stops while time advances
    r = tc.grade_timeline(samples)
    assert not r['ok'] and 'FREEZE' in codes(r)


def test_gap_is_detected():
    samples = timeline()
    samples[4]['t'] += 5.0                # a hole far larger than the cadence
    r = tc.grade_timeline(samples)
    assert not r['ok'] and 'GAP' in codes(r)


def test_reversal_is_detected():
    samples = timeline()
    samples[5]['t'] = samples[2]['t']     # time runs backwards as supplied
    r = tc.grade_timeline(samples)
    assert not r['ok'] and 'NON_MONOTONIC' in codes(r)


def test_duplicate_time_is_detected():
    samples = timeline()
    samples[4]['t'] = samples[3]['t']
    r = tc.grade_timeline(samples)
    assert not r['ok'] and 'DUPLICATE_T' in codes(r)


def test_under_coverage_is_detected():
    r = tc.grade_timeline(timeline(n=4), span=(0.0, 20.0))
    assert not r['ok'] and 'UNDER_COVERAGE' in codes(r)


def test_grade_frames_clean(tmp_path):
    for i in range(6):
        (tmp_path / f'f{i:05d}.png').write_bytes(f'frame-{i}'.encode())
    r = tc.grade_frames(tmp_path)
    assert r['ok'] and r['reward'] == 1.0, r


def test_grade_frames_index_gap(tmp_path):
    for i in (0, 1, 2, 5, 6):
        (tmp_path / f'f{i:05d}.png').write_bytes(f'frame-{i}'.encode())
    r = tc.grade_frames(tmp_path)
    assert not r['ok'] and 'INDEX_GAP' in codes(r)


def test_grade_frames_identical_frames(tmp_path):
    for i in range(6):
        (tmp_path / f'f{i:05d}.png').write_bytes(b'same-bytes')
    r = tc.grade_frames(tmp_path)
    assert not r['ok'] and 'IDENTICAL_FRAMES' in codes(r)


def test_grade_frames_missing_dir():
    r = tc.grade_frames(Path('/nonexistent/tinycontinuum'))
    assert not r['ok'] and r['reward'] == 0.0


def _chain(n=4):
    import hashlib
    out, prev = [], '0' * 64
    for i in range(n):
        h = hashlib.sha256(f'{prev}|{i}'.encode()).hexdigest()
        out.append({'seq': i, 'hash': h, 'prev': prev, 'output': f'result-{i}'})
        prev = h
    return out


def test_grade_chain_clean():
    r = tc.grade_chain(_chain())
    assert r['ok'] and r['reward'] == 1.0, r


def test_grade_chain_broken_link():
    c = _chain()
    c[2]['prev'] = 'f' * 64
    r = tc.grade_chain(c)
    assert not r['ok'] and 'BROKEN_LINK' in codes(r)


def test_grade_chain_truncated_payload():
    c = _chain()
    c[1]['output'] = 'x' * 500                # a round cap — the truncation tell
    r = tc.grade_chain(c)
    assert not r['ok'] and 'TRUNCATED_PAYLOAD' in codes(r)


def test_doctor():
    d = tc.doctor()
    assert d['ok'] and d['grades'] == ['timeline', 'frames', 'chain']
