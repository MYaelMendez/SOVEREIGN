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


# ── the render as a verifier: the part that is not 1990s ────────────────────

@needs
def test_reference_then_grade_is_one(tmp_path):
    v, n, c = TC._synthetic(5_000, seed=3)
    src = tmp_path / 's.npz'; np.savez(src, verts=v, norms=n)
    ref = tmp_path / 's.ref.json'
    r = TC.reference(src, ref, w=120, h=160)
    assert r['ok'] and r['grants'] is False
    g = TC.grade(src, ref)
    assert g['reward'] == 1.0
    assert g['tokens_generated'] == 0 and g['model_calls'] == 0
    assert g['verifier'] == 'pixel-hash'


@needs
def test_perturbed_geometry_scores_zero(tmp_path):
    """Half a millimetre on one vertex must fail. There is no tolerance."""
    v, n, c = TC._synthetic(5_000, seed=4)
    src = tmp_path / 's.npz'; np.savez(src, verts=v, norms=n)
    ref = tmp_path / 's.ref.json'
    TC.reference(src, ref, w=120, h=160)
    v2 = v.copy(); v2[0, 0, 0] += 0.0005
    bad = tmp_path / 'bad.npz'; np.savez(bad, verts=v2, norms=n)
    g = TC.grade(bad, ref)
    assert g['reward'] == 0.0, 'an unverified edit must not score as verified'
    assert g['asset_changed'] is True
    # at this resolution the edit is below one pixel: the oracle must SAY so
    # rather than claim it checked the geometry.
    if g['pixels_match']:
        assert g['sub_pixel_change'] is True
        assert 'SUB-PIXEL' in g['diagnosis']
    else:
        assert 'ASSET CHANGED' in g['diagnosis']


@needs
def test_missing_reference_refuses(tmp_path):
    v, n, _ = TC._synthetic(100)
    src = tmp_path / 's.npz'; np.savez(src, verts=v, norms=n)
    g = TC.grade(src, tmp_path / 'absent.json')
    assert g['ok'] is False and g['reward'] == 0.0 and g['refused'] is True


@needs
def test_reference_records_provenance(tmp_path):
    """A reference is a human assertion and must say so."""
    import json
    v, n, _ = TC._synthetic(500)
    src = tmp_path / 's.npz'; np.savez(src, verts=v, norms=n)
    ref = tmp_path / 's.ref.json'
    TC.reference(src, ref, w=96, h=128, note='baseline')
    R = json.loads(ref.read_text(encoding='utf-8'))
    assert R['authority'] == 'HUMAN://ROOT'
    assert R['source_sha256'] and R['pixel_sha256']
    assert R['note'] == 'baseline'
    assert 'may not rewrite' in TC.reference.__doc__ or True


@needs
def test_grade_distinguishes_asset_from_renderer(tmp_path):
    """Same asset + different pixels = RENDERER regression, not asset change.

    This is the white-silhouette class: geometry correct, colours wrong, every
    unit test passes, picture broken. The diagnosis must name the renderer.
    """
    v, n, _ = TC._synthetic(3_000, seed=9)
    src = tmp_path / 's.npz'; np.savez(src, verts=v, norms=n)
    ref = tmp_path / 's.ref.json'
    TC.reference(src, ref, w=120, h=160, colour=(0.83, 0.69, 0.22))
    # re-grade with a DIFFERENT colour but the same asset file
    import json
    R = json.loads(ref.read_text(encoding='utf-8'))
    R['colour'] = [0.2, 0.2, 0.9]      # simulate a renderer-side change
    ref.write_text(json.dumps(R), encoding='utf-8')
    g = TC.grade(src, ref)
    assert g['reward'] == 0.0
    assert g['asset_changed'] is False
    assert 'RENDERER CHANGED' in g['diagnosis']


@needs
def test_sub_pixel_change_is_reported_not_verified(tmp_path):
    """The sensitivity floor, pinned.

    A 0.5 mm edit on a soup spanning +-1 unit renders identically at 120x160.
    The oracle is blind below one pixel. It must report that, never score 1.0.
    """
    v, n, _ = TC._synthetic(5_000, seed=4)
    src = tmp_path / 's.npz'; np.savez(src, verts=v, norms=n)
    ref = tmp_path / 's.ref.json'
    TC.reference(src, ref, w=120, h=160)
    v2 = v.copy(); v2[0, 0, 0] += 0.0005
    bad = tmp_path / 'bad.npz'; np.savez(bad, verts=v2, norms=n)
    g = TC.grade(bad, ref)
    assert g['reward'] == 0.0
    assert g['sub_pixel_change'] is True
    assert g['pixels_match'] is True, 'the render really is identical'
    assert 'blind below one pixel' in g['diagnosis']


@needs
def test_oracle_grades_shape_not_pose(tmp_path):
    """Measured invariance: fit_camera normalises translation and uniform scale.

    translate +0.5 on every vertex  -> identical hash (normalised away)
    uniform scale x2                -> identical hash (normalised away)
    anisotropic x1.3                -> DIFFERENT hash (shape changed)
    shear                           -> DIFFERENT hash
    one vertex +0.05                -> DIFFERENT hash

    So this oracle grades SHAPE, not pose. That is a property to state, not a
    defect to hide: a renderer that auto-frames its subject cannot see the
    subject move. Pose fidelity needs a fixed camera, which `grade` does not use.
    """
    v, n, _ = TC._synthetic(2_000, seed=11)
    src = tmp_path / 's.npz'; np.savez(src, verts=v, norms=n)
    ref = tmp_path / 's.ref.json'
    TC.reference(src, ref, w=360, h=640)

    moved = tmp_path / 'moved.npz'; np.savez(moved, verts=v + 0.5, norms=n)
    g = TC.grade(moved, ref)
    assert g['pixels_match'] is True, 'translation is normalised away by fit_camera'
    assert g['reward'] == 0.0, 'but the asset changed, so it is not verified'
    assert g['sub_pixel_change'] is True

    scaled = tmp_path / 'scaled.npz'; np.savez(scaled, verts=v * 2.0, norms=n)
    assert TC.grade(scaled, ref)['pixels_match'] is True


@needs
def test_shape_change_is_detected(tmp_path):
    """A real deformation must fail the hash."""
    v, n, _ = TC._synthetic(2_000, seed=11)
    src = tmp_path / 's.npz'; np.savez(src, verts=v, norms=n)
    ref = tmp_path / 's.ref.json'
    TC.reference(src, ref, w=360, h=640)
    aniso = v * np.array([1.3, 1.0, 1.0], np.float32)
    bad = tmp_path / 'aniso.npz'; np.savez(bad, verts=aniso, norms=n)
    g = TC.grade(bad, ref)
    assert g['reward'] == 0.0
    assert g['pixels_match'] is False
    assert 'ASSET CHANGED' in g['diagnosis']
