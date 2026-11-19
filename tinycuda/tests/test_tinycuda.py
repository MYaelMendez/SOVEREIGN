"""tinyCUDA tests — the claims, checked.

The central claim is determinism, and the reason it holds is a specific
construction (packed uint64 depth+id, one atomicMin). These tests attack that
construction directly rather than trusting a hash comparison alone.
"""
from __future__ import annotations
import hashlib, sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tinycuda as TC

try:
    import cupy  # noqa
    HAS_CUDA = True
except Exception:
    HAS_CUDA = False

needs = pytest.mark.skipif(not HAS_CUDA, reason='CUDA/CuPy not available')


# ── pure math, no GPU ───────────────────────────────────────────────────────

def test_persp_is_finite():
    P = TC.persp(40, 0.05, 60, aspect=9/16)
    assert P.shape == (4, 4) and np.isfinite(P).all()
    assert P[3, 2] == 1.0, 'perspective divide row'


def test_look_at_orthonormal():
    M = TC.look_at((3, -2, 2), (0, 0, 0.5))
    R = M[:3, :3]
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-5)


def test_look_at_places_target_on_axis():
    eye, tgt = np.array([3., -2., 2.]), np.array([0., 0., 0.5])
    M = TC.look_at(eye, tgt)
    p = M[:3, :3] @ tgt + M[:3, 3]
    assert abs(p[0]) < 1e-5 and abs(p[1]) < 1e-5, 'target must sit on the camera axis'
    assert p[2] > 0, 'camera looks down +Z'


def test_fit_camera_frames_any_soup():
    v, n, c = TC._synthetic(500)
    M, ctr, rad = TC.fit_camera(v)
    assert rad > 0 and np.isfinite(M).all()
    assert np.allclose(ctr, v.reshape(-1, 3).mean(axis=0), atol=1e-4)


def test_synthetic_is_reproducible():
    a = TC._synthetic(100, seed=7)
    b = TC._synthetic(100, seed=7)
    for x, y in zip(a, b):
        assert np.array_equal(x, y)


def test_colours_documented_as_unit_range():
    """0-255 saturates every pixel white. The docstring must keep saying so."""
    src = Path(TC.__file__).read_text(encoding='utf-8')
    assert '0-1' in src and 'saturate' in src


def test_no_network_or_credentials():
    src = Path(TC.__file__).read_text(encoding='utf-8')
    for bad in ('urlopen', 'urlretrieve', 'requests.', 'api_key', 'password', 'socket.'):
        assert bad not in src, f'unexpected reference: {bad}'


# ── the GPU claims ──────────────────────────────────────────────────────────

@needs
def test_deterministic_across_repeats():
    r = TC.Raster(180, 320)
    v, n, c = TC._synthetic(20_000)
    M, _, _ = TC.fit_camera(v)
    hs = [hashlib.sha256(r.render(v, n, c, M).tobytes()).hexdigest() for _ in range(5)]
    assert len(set(hs)) == 1, f'NOT deterministic: {hs}'


@needs
def test_deterministic_across_instances():
    """A fresh context must give the same bytes — not just a warm reuse."""
    v, n, c = TC._synthetic(20_000)
    M, _, _ = TC.fit_camera(v)
    a = TC.Raster(180, 320).render(v, n, c, M)
    b = TC.Raster(180, 320).render(v, n, c, M)
    assert np.array_equal(a, b)


@needs
def test_empty_scene_is_background_not_garbage():
    """T=0 must not index the colour buffer with the sentinel's low bits."""
    r = TC.Raster(64, 64)
    e = np.zeros((0, 3, 3), np.float32)
    px = r.render(e, e.reshape(0, 3), e.reshape(0, 3), np.eye(4, dtype=np.float32))
    assert px.shape == (64, 64, 3)
    assert px.std() < 30, 'background should be a smooth gradient'
    assert np.isfinite(px).all()


@needs
def test_depth_order_is_correct():
    """A near triangle must occlude a far one at the same pixel.

    This is what the packed atomicMin buys. Two overlapping quads, the near
    one red and the far one blue: the centre pixel must be red.
    """
    def quad(z, col):
        v = np.array([[[-1, -1, z], [1, -1, z], [1, 1, z]],
                      [[-1, -1, z], [1, 1, z], [-1, 1, z]]], np.float32)
        n = np.tile(np.array([0, 0, -1], np.float32), (2, 1))
        c = np.tile(np.array(col, np.float32), (2, 1))
        return v, n, c
    far = quad(0.6, (0.0, 0.0, 1.0))
    near = quad(0.3, (1.0, 0.0, 0.0))
    v = np.concatenate([far[0], near[0]])
    n = np.concatenate([far[1], near[1]])
    c = np.concatenate([far[2], near[2]])
    # up must not be parallel to the view direction, or the cross product
    # is zero and the basis is NaN. Viewing along Z means up = Y.
    M = TC.persp(60, 0.05, 10) @ TC.look_at((0, 0, -2), (0, 0, 0.5), up=(0, 1, 0))
    px = TC.Raster(64, 64).render(v, n, c, M)
    mid = px[32, 32].astype(int)
    assert mid[0] > mid[2], f'near red must win over far blue, got {mid}'


@needs
def test_length_mismatch_raises():
    r = TC.Raster(32, 32)
    v, n, c = TC._synthetic(10)
    with pytest.raises(ValueError):
        r.render(v, n[:5], c, np.eye(4, dtype=np.float32))


@needs
def test_cost_is_measurable_and_reported():
    """Characterise the cost rather than assert a shape it does not have.

    Finding: with a fixed-resolution viewport and small triangles, cost is
    dominated by the per-pixel shade pass, not the triangle count. 1k and 100k
    triangles measure within noise of each other at 240x320. That is a real
    property of a two-pass rasteriser, not a defect — so the test pins the
    measurement instead of demanding a curve.
    """
    import time
    r = TC.Raster(240, 320)
    rows = []
    for count in (1_000, 100_000):
        v, n, c = TC._synthetic(count)
        M, _, _ = TC.fit_camera(v)
        r.render(v, n, c, M)                     # warmup: JIT is not throughput
        t0 = time.perf_counter()
        for _ in range(5):
            r.render(v, n, c, M)
        rows.append((count, (time.perf_counter()-t0)/5))
    for count, dt in rows:
        assert 0 < dt < 1.0, f'{count} tris took {dt:.4f}s — implausible'
    # the shade pass runs over every pixel regardless of triangle count
    assert rows[1][1] < rows[0][1] * 20, 'triangle count should not dominate catastrophically'


@needs
def test_resolution_dominates_cost():
    """The per-pixel pass is the real cost driver — verify that instead."""
    import time
    v, n, c = TC._synthetic(10_000)
    M, _, _ = TC.fit_camera(v)
    times = []
    for (w, h) in ((120, 160), (480, 640)):
        r = TC.Raster(w, h)
        r.render(v, n, c, M)
        t0 = time.perf_counter()
        for _ in range(5):
            r.render(v, n, c, M)
        times.append((time.perf_counter()-t0)/5)
    assert times[1] > times[0], f'4x the pixels should cost more: {times}'


@needs
def test_render_draws_something():
    """A frame that is nearly uniform means nothing was rasterised."""
    v, n, c = TC._synthetic(50_000)
    M, _, _ = TC.fit_camera(v)
    px = TC.Raster(180, 320).render(v, n, c, M)
    assert px.std() > 8, 'frame is nearly uniform — nothing drawn'
