"""tinyPython tests — the claims, checked.

Each test maps to a claim in the README. Run: pytest -q
Tests skip cleanly when the policy or MuJoCo is absent, rather than silently
passing.
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tinypython as TP

try:
    import mujoco, onnxruntime  # noqa
    HAS_DEPS = True
except Exception:
    HAS_DEPS = False

_d = TP.doctor() if HAS_DEPS else {'ok': False}
HAS_ASSETS = bool(_d.get('ok'))

needs = pytest.mark.skipif(not (HAS_DEPS and HAS_ASSETS),
                           reason='policy/MJCF/mujoco/onnxruntime not available')


# ── the inference contract ──────────────────────────────────────────────────

def test_contract_shapes():
    assert len(TP.JOINTS) == 23
    assert TP.DEFAULT_POS.shape == (23,)
    assert TP.KP.shape == TP.KD.shape == TP.TAU_LIMIT.shape == (23,)
    assert len(TP.SLOTS) == 3
    assert sum(len(s) for s in TP.SLOTS) == 23, 'slots must partition the joints'
    assert TP.POLICY_DT == 0.02 and TP.SUBSTEPS == 4
    assert TP.ACTION_LAG == 2


def test_slots_are_a_partition():
    flat = [i for s in TP.SLOTS for i in s]
    assert sorted(flat) == list(range(23)), 'a joint is missing or duplicated'


def test_quat_identity():
    assert np.allclose(TP.quat_to_mat([1, 0, 0, 0]), np.eye(3))


def test_quat_is_orthonormal():
    for q in ([0.7071, 0.7071, 0, 0], [0.5, 0.5, 0.5, 0.5], [0.9, 0.1, 0.2, 0.3]):
        R = TP.quat_to_mat(q)
        assert np.allclose(R @ R.T, np.eye(3), atol=1e-5)
        assert abs(np.linalg.det(R) - 1) < 1e-5


def test_quat_handles_zero():
    """A degenerate quaternion must not produce NaNs."""
    R = TP.quat_to_mat([0, 0, 0, 0])
    assert not np.isnan(R).any()


# ── governance ──────────────────────────────────────────────────────────────

def test_no_hardware_path():
    """Nothing here may address a motor, a socket, or a serial port."""
    src = Path(TP.__file__).read_text(encoding='utf-8')
    for bad in ('serial.', 'socket.', 'pyserial', 'rospy', 'rclpy',
                'requests.', 'urlopen', 'api_key', 'password'):
        assert bad not in src, f'hardware/network reference: {bad!r}'


def test_missing_policy_refuses(tmp_path):
    """A missing asset is a structured refusal, not a crash or a silent pass."""
    import os
    old = os.environ.get('TINYPYTHON_ASSETS')
    os.environ['TINYPYTHON_ASSETS'] = str(tmp_path)
    try:
        r = TP.walk(tmp_path / 'x.json')
        assert r['ok'] is False and r['refused'] is True
        assert r['grants'] is False
        assert 'missing' in r['reason']
    finally:
        if old is None:
            os.environ.pop('TINYPYTHON_ASSETS', None)
        else:
            os.environ['TINYPYTHON_ASSETS'] = old


# ── the walk itself ─────────────────────────────────────────────────────────

@needs
def test_walk_reproduces_the_reference(tmp_path):
    """The published proof: 12 s at vx 0.4 -> +4.1868 m, no fall."""
    r = TP.walk(tmp_path / 'w.json', vx=0.4, duration=12.0)
    assert r['ok'] is True, r
    assert r['fell_at'] is None
    assert abs(r['base_x'] - 4.1868) < 0.01, f"travel drifted: {r['base_x']}"
    assert abs(r['min_z'] - 0.6125) < 0.01
    assert r['ticks'] == 600 and r['steps'] == 2400
    assert r['grants'] is False and r['executed'] is False and r['hardware'] is False


@needs
def test_walk_is_deterministic(tmp_path):
    a = TP.walk(tmp_path / 'a.json', vx=0.4, duration=4.0)
    b = TP.walk(tmp_path / 'b.json', vx=0.4, duration=4.0)
    assert a['receipt'] == b['receipt'], 'same command must give the same trace'


@needs
def test_standing_is_success(tmp_path):
    """Regression: a forward-only test wrongly failed a standing robot."""
    r = TP.walk(tmp_path / 's.json', vx=0.0, vy=0.0, wz=0.0, duration=6.0)
    assert r['upright'] is True
    assert r['obeyed_command'] is True, 'standing still is a correct behaviour'
    assert r['ok'] is True


@needs
def test_backward_is_success(tmp_path):
    """Regression: walking backward was scored a failure."""
    r = TP.walk(tmp_path / 'b.json', vx=-0.2, duration=6.0)
    assert r['base_x'] < -0.05
    assert r['ok'] is True, 'moving in the commanded direction is success'


@needs
def test_lateral_measures_the_commanded_axis(tmp_path):
    """Regression: a strafe moved +1.79 m in y and was scored on x."""
    r = TP.walk(tmp_path / 'l.json', vx=0.0, vy=0.3, duration=6.0)
    v = TP.verify(Path(r['trace']))
    assert abs(v['travel_y_m']) > 0.3, 'the robot should strafe'
    assert v['ok'] is True


@needs
def test_verify_recomputes(tmp_path):
    """verify must not read the trace's own success flag."""
    r = TP.walk(tmp_path / 'v.json', vx=0.4, duration=6.0)
    p = Path(r['trace'])
    d = json.loads(p.read_text(encoding='utf-8'))
    d['success'] = False                      # lie in the flag
    p.write_text(json.dumps(d), encoding='utf-8')
    v = TP.verify(p)
    assert v['claims_success'] is False
    assert v['ok'] is True, 'verify must recompute from the geometry'
    assert v['agrees_with_claim'] is False


@needs
def test_gait_is_a_shuffle_not_a_stride(tmp_path):
    """Documented finding: knees flex ~46 deg but feet barely clear the ground.

    Nobody rewarded foot clearance, so the policy never learned to lift its
    feet. This test pins the observation so a future policy change is noticed.
    """
    r = TP.walk(tmp_path / 'g.json', vx=0.45, duration=8.0)
    d = json.loads(Path(r['trace']).read_text(encoding='utf-8'))
    q = np.array(d['qpos'])[:, 7:30]
    knee_swing = float(np.degrees(q[:, 3].max() - q[:, 3].min()))
    assert knee_swing > 30, 'the knee should flex substantially'
    assert knee_swing < 90, 'gait character changed — re-measure and update the docs'
