"""tinyMUJOCO tests — contracts, not snapshots.

Timing is deliberately absent: throughput is a measurement, not a correctness
property. A test that goes red because the machine was busy trains you to
ignore red.

Two models, because they test different things:
  SPHERE    free joint, nu=0 — pure open-loop dynamics. Seeding CANNOT change it.
  ACTUATED  a hinge with a motor — the seed drives real control.
Asserting that a seed changes an unactuated model would assert a false property.
"""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tinymujoco as tm  # noqa: E402

MJ, ERR = tm._mj()
pytestmark = pytest.mark.skipif(ERR is not None, reason=f'mujoco unavailable: {ERR}')

SPHERE = ('<mujoco><worldbody><body><geom type="sphere" size="0.1"/>'
          '<joint type="free"/></body></worldbody></mujoco>')

ACTUATED = ('<mujoco><worldbody>'
            '<body pos="0 0 1"><geom type="capsule" fromto="0 0 0 0 0 -0.3" size="0.04"/>'
            '<joint name="hip" type="hinge" axis="0 1 0"/></body>'
            '</worldbody>'
            '<actuator><motor name="hip_m" joint="hip" gear="1"/></actuator></mujoco>')


@pytest.fixture
def model(tmp_path):
    p = tmp_path / 'sphere.xml'
    p.write_text(SPHERE, encoding='utf-8')
    return p


@pytest.fixture
def actuated(tmp_path):
    p = tmp_path / 'actuated.xml'
    p.write_text(ACTUATED, encoding='utf-8')
    return p


def test_doctor_probes_the_live_system():
    d = tm.doctor()
    assert d['ok'] is True
    assert d['checks']['mujoco'] == MJ.__version__
    assert d['checks']['opengl_required'] is False
    assert d['checks']['headless'] is True
    assert d['grants'] is False


def test_rollout_is_deterministic(model, tmp_path):
    a = tm.rollout(model, seed=0, steps=120, out=tmp_path / 'a.npy')
    b = tm.rollout(model, seed=0, steps=120, out=tmp_path / 'b.npy')
    assert a['ok'] and b['ok']
    assert a['trace_sha256'] == b['trace_sha256']
    assert np.array_equal(np.load(tmp_path / 'a.npy'), np.load(tmp_path / 'b.npy'))


def test_actuated_rollout_is_deterministic(actuated, tmp_path):
    a = tm.rollout(actuated, seed=3, steps=120, out=tmp_path / 'a.npy')
    b = tm.rollout(actuated, seed=3, steps=120, out=tmp_path / 'b.npy')
    assert a['trace_sha256'] == b['trace_sha256']


def test_different_seed_differs_when_actuated(actuated):
    a = tm.rollout(actuated, seed=0, steps=120)
    b = tm.rollout(actuated, seed=1, steps=120)
    assert a['seed_affects_motion'] is True
    assert a['trace_sha256'] != b['trace_sha256']


def test_unactuated_model_reports_seeding_is_inert(model):
    r = tm.rollout(model, steps=20)
    assert r['nu'] == 0
    assert r['controllable'] is False
    assert r['seed_affects_motion'] is False
    assert 'no actuators' in r['note']


def test_trace_shape_matches_steps_and_nq(model):
    r = tm.rollout(model, seed=0, steps=77)
    assert r['steps'] == 77
    assert r['nq'] == 7


def test_qpos0_records_the_initial_condition(model):
    q0 = [1.0, 2.0, 3.0, 1.0, 0.0, 0.0, 0.0]
    r = tm.rollout(model, steps=1, qpos0=q0)
    assert r['ok'] is True
    assert r['qpos0'] == q0


def test_bad_qpos0_shape_is_refused(model):
    r = tm.rollout(model, steps=10, qpos0=[0.0, 0.0, 1.0])
    assert r['ok'] is False and r['refused'] is True
    assert 'qpos0 shape' in r['reason']


def test_model_hash_travels_with_the_trace(model):
    r = tm.rollout(model, steps=10)
    assert r['model_sha256'] == hashlib.sha256(model.read_bytes()).hexdigest()


def test_editing_the_model_changes_its_hash(tmp_path):
    p = tmp_path / 'a.xml'; p.write_text(SPHERE, encoding='utf-8')
    q = tmp_path / 'b.xml'
    q.write_text(SPHERE.replace('size="0.1"', 'size="0.2"'), encoding='utf-8')
    assert tm.rollout(p, steps=10)['model_sha256'] != tm.rollout(q, steps=10)['model_sha256']


def test_grant_is_never_implied(model, tmp_path):
    r = tm.rollout(model, steps=20, out=tmp_path / 't.npy')
    assert r['grants'] is False
    assert r['executed'] is False
    assert r['hardware'] is False


def test_missing_model_is_refused(tmp_path):
    r = tm.rollout(tmp_path / 'nope.xml')
    assert r['ok'] is False and r['refused'] is True
    assert 'no such model' in r['reason']


def test_malformed_model_is_refused(tmp_path):
    p = tmp_path / 'bad.xml'
    p.write_text('<mujoco><not-a-real-tag/></mujoco>', encoding='utf-8')
    r = tm.rollout(p)
    assert r['ok'] is False and r['refused'] is True


def test_reference_verifies_determinism(actuated, tmp_path):
    r = tm.reference(actuated, seed=0, steps=100, out=tmp_path / 'ref.npy')
    assert r['ok'] is True
    assert r['verified_deterministic'] is True
    assert r['reference'] is True


def test_grade_identical_scores_one(actuated, tmp_path):
    tm.reference(actuated, seed=0, steps=100, out=tmp_path / 'ref.npy')
    tm.rollout(actuated, seed=0, steps=100, out=tmp_path / 'cand.npy')
    g = tm.grade(tmp_path / 'cand.npy', tmp_path / 'ref.npy')
    assert g['ok'] is True
    assert g['reward'] == 1.0
    assert g['identical'] is True
    assert g['max_abs_diff'] == 0.0
    assert g['tokens_used'] == 0 and g['model_calls'] == 0


def test_grade_different_seed_scores_zero(actuated, tmp_path):
    tm.reference(actuated, seed=0, steps=100, out=tmp_path / 'ref.npy')
    tm.rollout(actuated, seed=9, steps=100, out=tmp_path / 'cand.npy')
    g = tm.grade(tmp_path / 'cand.npy', tmp_path / 'ref.npy')
    assert g['reward'] == 0.0
    assert g['identical'] is False
    assert g['differing_elements'] > 0


def test_grade_refuses_a_prefix(actuated, tmp_path):
    tm.reference(actuated, seed=0, steps=100, out=tmp_path / 'ref.npy')
    tm.rollout(actuated, seed=0, steps=50, out=tmp_path / 'short.npy')
    g = tm.grade(tmp_path / 'short.npy', tmp_path / 'ref.npy')
    assert g['ok'] is False and g['refused'] is True
    assert g['reward'] == 0.0
    assert 'prefix is not a reproduction' in g['reason']


def test_grade_detects_a_single_element_edit(actuated, tmp_path):
    tm.reference(actuated, seed=0, steps=100, out=tmp_path / 'ref.npy')
    a = np.load(tmp_path / 'ref.npy').copy()
    a[50, 0] += 1e-12
    np.save(tmp_path / 'edited.npy', a)
    g = tm.grade(tmp_path / 'edited.npy', tmp_path / 'ref.npy')
    assert g['reward'] == 0.0
    assert g['differing_elements'] == 1
    assert g['max_abs_diff'] > 0.0


def test_grade_refuses_missing_files(tmp_path):
    g = tm.grade(tmp_path / 'a.npy', tmp_path / 'b.npy')
    assert g['ok'] is False and g['refused'] is True


def test_grade_refuses_non_npy(tmp_path):
    p = tmp_path / 'x.npy'; p.write_text('not an array', encoding='utf-8')
    q = tmp_path / 'y.npy'; np.save(q, np.zeros((3, 3)))
    g = tm.grade(p, q)
    assert g['ok'] is False and g['refused'] is True


def test_bench_reports_measurements(actuated):
    b = tm.bench(actuated, sizes=(100, 200), reps=1)
    assert b['ok'] is True
    assert len(b['rows']) == 2
    for r in b['rows']:
        assert r['steps_per_s'] > 0
        assert r['realtime_factor'] > 0
