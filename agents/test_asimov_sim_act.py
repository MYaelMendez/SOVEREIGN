"""Task 2 (tinyACTOR): twin sim and hardware act must be different facts.

Skill contract (robot-protocol-stack):
  sim  -> may drive the TWIN to completion: executed:true, hardware:false, grants:false
  exec -> real body: require_approval, granted:false until a bound card is verified
  A verb must never name both.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('asimov_protocol',
                                             'C:/æ/agents/asimov_protocol.py')
ap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ap)


def test_sim_reports_twin_not_hardware():
    r = ap.dispatch('asimov://sim set_velocity')
    assert r['hardware'] is False
    assert r['grants'] is False
    assert r['sim']['engine'] == 'MuJoCo'


def test_sim_executes_on_twin_and_reports_it():
    """The current sim is plan-only; the contract requires honest twin execution."""
    r = ap.dispatch('asimov://sim set_velocity')
    assert r['executed'] is True, 'twin rollout must be reported as executed'
    assert r['hardware'] is False


def test_exec_requires_grant_and_never_self_grants():
    r = ap.dispatch('asimov://exec set_velocity')
    assert r.get('granted', False) is False
    assert r.get('decision') in ('require_approval', 'refused', None)


def test_sim_and_exec_addresses_differ():
    a = ap.dispatch('asimov://sim set_velocity')
    b = ap.dispatch('asimov://exec set_velocity')
    assert a['address'] != b['address']
