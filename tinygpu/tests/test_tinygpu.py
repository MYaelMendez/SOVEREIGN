"""tinyGPU tests — the claims, checked.

Every test here corresponds to a claim in README/RESULTS. A claim with no test
is marketing. Run: pytest -q

The GPU tests skip cleanly when CUDA is absent, so the suite is meaningful on a
machine without an NVIDIA card rather than silently passing.
"""
from __future__ import annotations
import hashlib, json, math, sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tinygpu as T

HERE = Path(__file__).resolve().parents[1]
MODEL = HERE / 'model'
HAS_MODEL = (MODEL / 'urdf.json').exists()

try:
    import cupy  # noqa
    HAS_CUDA = True
except Exception:
    HAS_CUDA = False

needs_cuda = pytest.mark.skipif(not HAS_CUDA, reason='CUDA/CuPy not available')
needs_model = pytest.mark.skipif(not HAS_MODEL, reason='model not fetched; run tinygpu fetch')


# ── the schema claims ───────────────────────────────────────────────────────

@needs_model
def test_urdf_schema_is_what_we_say():
    """26 links, 25 joints, joints is a LIST, links carry 'mesh' not 'stl'."""
    u = json.loads((MODEL / 'urdf.json').read_text(encoding='utf-8'))
    assert len(u['links']) == 26, 'link count changed'
    assert len(u['joints']) == 25, 'joint count changed'
    assert isinstance(u['joints'], list), 'joints must be a LIST, not a dict'
    first = next(iter(u['links'].values()))
    assert 'mesh' in first, "links use 'mesh'; 'stl' was an invented field"
    for j in u['joints']:
        assert {'name', 'parent', 'child', 'xyz', 'rpy'} <= set(j)


@needs_model
def test_every_link_has_a_mesh_file():
    """No silent missing geometry. A missing mesh must be loud, not skipped."""
    u, meshes = T.load_model(MODEL)
    named = [n for n, i in u['links'].items() if i.get('mesh')]
    assert len(meshes) == len(named), f'{len(named)-len(meshes)} meshes failed to load'


# ── kinematics ──────────────────────────────────────────────────────────────

def test_rpy_identity():
    assert np.allclose(T.rpy(0, 0, 0), np.eye(3))


def test_rpy_is_orthonormal():
    for a in [(0.3, -0.2, 0.7), (1.1, 0.0, -2.4), (0, math.pi / 2, 0)]:
        R = T.rpy(*a)
        assert np.allclose(R @ R.T, np.eye(3), atol=1e-9)
        assert abs(np.linalg.det(R) - 1) < 1e-9


def test_axis_angle_zero_is_identity():
    assert np.allclose(T.axis_angle([0, 1, 0], 0.0), np.eye(3))


def test_axis_angle_degenerate_axis_is_identity():
    """A zero-length axis must not produce NaNs."""
    R = T.axis_angle([0, 0, 0], 1.0)
    assert np.allclose(R, np.eye(3))
    assert not np.isnan(R).any()


def test_axis_angle_quarter_turn():
    R = T.axis_angle([0, 0, 1], math.pi / 2)
    assert np.allclose(R @ np.array([1, 0, 0]), [0, 1, 0], atol=1e-9)


@needs_model
def test_fk_places_every_link():
    u, _ = T.load_model(MODEL)
    xf = T.world_transforms(u, {})
    assert len(xf) == len(u['links']), 'forward kinematics left links unplaced'
    for M in xf.values():
        assert M.shape == (4, 4)
        assert not np.isnan(M).any()
        assert np.allclose(M[:3, :3] @ M[:3, :3].T, np.eye(3), atol=1e-7)


@needs_model
def test_fk_responds_to_joint_angles():
    """A pose must actually change the geometry, or the film is a still."""
    u, _ = T.load_model(MODEL)
    a = T.world_transforms(u, {})
    jn = next(j['name'] for j in u['joints'] if 'shoulder_pitch' in j['name'])
    b = T.world_transforms(u, {jn: 0.5})
    moved = [k for k in a if not np.allclose(a[k], b[k])]
    assert moved, 'no link moved when a joint was rotated'


# ── the colour-range bug that passed every gate ─────────────────────────────

def test_colours_are_normalised():
    """The shade kernel wants 0-1. 0-255 saturates every pixel to white.

    This produced a VALID MP4 with correct geometry that looked like a flat
    silhouette, and the luminance gate passed it. Regression guard.
    """
    gold = np.array(T.GOLD, float) / 255.0
    assert gold.max() <= 1.0
    assert gold.min() >= 0.0
    src = (HERE / 'tinygpu.py').read_text(encoding='utf-8')
    assert '/255.0' in src or '/ 255.0' in src, 'colour normalisation was removed'


# ── determinism: the headline claim ─────────────────────────────────────────

@needs_cuda
@needs_model
def test_render_is_deterministic(tmp_path):
    """Same model + same poses -> byte-identical frames.

    The depth test packs depth and triangle id into one uint64 atomicMin, so
    there is no read-modify-write race between the depth and colour passes.
    """
    from rtx_raster import RtxRenderer, persp, look_at
    u, meshes = T.load_model(MODEL)
    tris, nrms, cols = [], [], []
    for name, (mv, mn) in meshes.items():
        tris.append(mv); nrms.append(mn)
        cols.append(np.tile(np.array(T.GOLD, float) / 255.0, (len(mv), 1)))
    v = np.concatenate(tris).astype(np.float32)
    n = np.concatenate(nrms).astype(np.float32)
    c = np.concatenate(cols).astype(np.float32)
    lift = -float(v[:, :, 2].min())
    P = persp(40.0, 0.05, 60.0, aspect=9 / 16)
    V = look_at((3.2, -2.8, 2.0 + lift), (0, 0, 0.55 + lift))
    mvp = (P @ V).astype(np.float32)
    r = RtxRenderer(180, 320)
    hashes = []
    for _ in range(3):
        px = r.render(v, n, c, mvp)
        hashes.append(hashlib.sha256(px.tobytes()).hexdigest())
    assert len(set(hashes)) == 1, f'render is NOT deterministic: {hashes}'


@needs_cuda
@needs_model
def test_geometry_is_not_empty(tmp_path):
    """A render that draws nothing must fail, not pass a luminance gate."""
    from rtx_raster import RtxRenderer, persp, look_at
    u, meshes = T.load_model(MODEL)
    tris = [mv for mv, _ in meshes.values()]
    v = np.concatenate(tris).astype(np.float32)
    n = np.concatenate([mn for _, mn in meshes.values()]).astype(np.float32)
    c = np.tile(np.array(T.GOLD, float) / 255.0, (len(v), 1)).astype(np.float32)
    lift = -float(v[:, :, 2].min())
    P = persp(40.0, 0.05, 60.0, aspect=9 / 16)
    V = look_at((3.2, -2.8, 2.0 + lift), (0, 0, 0.55 + lift))
    r = RtxRenderer(180, 320)
    px = r.render(v, n, c, (P @ V).astype(np.float32))
    # the robot must occupy a real fraction of the frame, and not be uniform
    assert px.std() > 8, 'frame is nearly uniform — nothing was drawn'
    assert len(v) > 500_000, f'triangle count collapsed to {len(v)}'


# ── honesty of the tooling ──────────────────────────────────────────────────

def test_doctor_reports_measurement_not_assumption():
    d = T.doctor()
    assert 'checks' in d
    if HAS_CUDA:
        assert d['ok'] is True
        assert 'matmul' in d['checks'], 'doctor must prove compute, not just enumerate'
        assert d['checks']['matmul']['gflops'] > 0
    else:
        assert d['ok'] is False
        assert 'fix' in d['checks']['cuda'], 'a failure must name its remedy'


def test_no_credentials_or_network_at_render_time():
    """The render path must not reach the network or read a secret."""
    src = (HERE / 'tinygpu.py').read_text(encoding='utf-8')
    body = src[src.index('def render('):src.index('def verify(')]
    for bad in ('urlopen', 'urlretrieve', 'requests.', 'api_key', 'token', 'password'):
        assert bad not in body, f'render path references {bad!r}'


def test_fetch_is_the_only_network_path():
    src = (HERE / 'tinygpu.py').read_text(encoding='utf-8')
    assert 'urlretrieve' in src[src.index('def fetch('):src.index('def load_model(')]
    assert src.count('urlretrieve') == 2, 'network calls must stay inside fetch()'
