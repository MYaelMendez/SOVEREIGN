"""Plan verb gate — refuses invented verbs, accepts real ones and refusals."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

sp = importlib.util.spec_from_file_location('g', 'C:/æ/agents/plan_verb_gate.py')
g = importlib.util.module_from_spec(sp); sp.loader.exec_module(g)


def test_v2_defect_is_refused():
    r = g.gate('action: move_camera\ntarget: camera_id:0\naction_type: pan')
    assert r['verdict'] == 'REFUSE' and 'move_camera' in r['invented_verbs']
    assert r['granted'] is False


def test_clean_refusal_accepts_mention():
    r = g.gate('REFUSED — move_camera is not on the wire. Use photo or capture_clip.')
    assert r['verdict'] == 'ACCEPT' and r['invented_verbs'] == []


def test_real_verbs_accept():
    r = g.gate('action: status\nverb: state\nplan stand')
    assert r['verdict'] == 'ACCEPT' and r['granted'] is False


def test_walk_is_not_a_wire_verb():
    r = g.gate('action: walk\ntarget: door')
    assert r['verdict'] == 'REFUSE' and 'walk' in r['invented_verbs']


def test_canonical_table_is_the_authority():
    assert len(g.VERBS) == 14
    assert 'set_joints' in g.VERBS and 'move_camera' not in g.VERBS
