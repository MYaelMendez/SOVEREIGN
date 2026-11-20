"""tinyCUDAVIDEO tests.

The load-bearing test is test_frozen_tail_is_rejected: it constructs the exact
defect that shipped three times — picture shorter than audio — and asserts the
gate refuses it. Every other pixel check would pass that film.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tinycudavideo as V

FF = V._ffmpeg()
FFMPEG = FF / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
FFPROBE = FF / ('ffprobe.exe' if os.name == 'nt' else 'ffprobe')


def _frames(n=24, w=180, h=320, seed=0):
    """Bright, high-contrast, genuinely moving frames — passes the pixel gate."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        a = np.full((h, w, 3), 60, np.uint8)
        y = int((i / max(1, n - 1)) * (h - 60))
        a[y:y + 60] = (230, 200, 90)
        a += rng.integers(0, 40, (h, w, 3), dtype=np.uint8)
        out.append(a)
    return out


@pytest.fixture(scope='module')
def good(tmp_path_factory):
    d = tmp_path_factory.mktemp('tcv')
    r = V.produce(_frames(), d / 'good.mp4', fps=24)
    return d, r


def test_doctor_reports_real_capability():
    d = V.doctor()
    assert 'gate' in d and d['gate']['mux_tolerance_s'] == V.MUX_TOLERANCE_S
    assert isinstance(d['ok'], bool)
    # never claim nvenc without probing the encoder list
    if d['ok']:
        assert d['nvenc'] is True and d['cupy'] is not None


def test_produce_silent_film_passes(good):
    d, r = good
    assert r['ok'], r.get('reason')
    assert r['gate']['mux']['audio_s'] is None
    assert r['frames_rendered'] == 24


def test_gate_records_the_measurement_scale(good):
    d, r = good
    px = r['gate']['pixels']
    assert px['analysis_scale'] == [180, 320]      # native for these frames
    assert px['sampled'] > 0


def test_downscale_is_a_different_instrument(good):
    """The bug this module shipped with: thresholds calibrated at native res
    applied to a downscaled measurement. The two must not be equal, and the
    scale must be recorded so nobody compares them silently."""
    d, _ = good
    native = V.gate(d / 'good.mp4')
    small = V.gate(d / 'good.mp4', scale=(90, 160))
    assert native['pixels']['analysis_scale'] != small['pixels']['analysis_scale']
    assert small['pixels']['analysis_scale'] == [90, 160]


def test_frozen_tail_is_rejected(tmp_path):
    """THE defect. 1 s of picture muxed against 3 s of audio. Every pixel check
    passes; only the mux check can see it."""
    fd = tmp_path / 'f'
    fd.mkdir()
    from PIL import Image
    fr = _frames(n=24)
    for i, a in enumerate(fr):
        Image.fromarray(a).save(fd / f'f{i:05d}.png')
    aud = tmp_path / 'a.wav'
    subprocess.run([str(FFMPEG), '-y', '-v', 'error', '-f', 'lavfi',
                    '-i', 'sine=frequency=440:duration=3', str(aud)],
                   check=True, timeout=180)
    bad = tmp_path / 'frozen.mp4'
    # the OLD behaviour: -t = audio length, picture runs out
    subprocess.run([str(FFMPEG), '-y', '-v', 'error', '-framerate', '24',
                    '-i', str(fd / 'f%05d.png'), '-i', str(aud),
                    '-c:v', 'h264_nvenc', '-preset', 'p5', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-t', '3.000', str(bad)], check=True, timeout=300)
    g = V.gate(bad)
    assert g['mux']['frozen_tail_s'] > 1.5
    assert g['checks']['mux_match'] is False
    assert g['ok'] is False
    assert 'mux_match' in g['failed']
    # and the pixel half genuinely passes — that is why it shipped
    assert g['checks']['luminance'] and g['checks']['contrast']


def test_produce_loops_picture_to_cover_audio(tmp_path):
    aud = tmp_path / 'a.wav'
    subprocess.run([str(FFMPEG), '-y', '-v', 'error', '-f', 'lavfi',
                    '-i', 'sine=frequency=440:duration=3', str(aud)],
                   check=True, timeout=180)
    r = V.produce(_frames(n=24), tmp_path / 'covered.mp4', fps=24, audio=aud)
    assert r['picture_loops'] == 3, r
    assert r['ok'], r.get('reason')
    assert r['gate']['mux']['frozen_tail_s'] <= V.MUX_TOLERANCE_S


def test_produce_refuses_a_black_film(tmp_path):
    """Thresholds are never lowered to pass. A black film must be refused."""
    black = [np.zeros((320, 180, 3), np.uint8) for _ in range(24)]
    r = V.produce(black, tmp_path / 'black.mp4', fps=24)
    assert r['ok'] is False
    assert r.get('refused') is True
    assert 'luminance' in r['gate']['failed']


def test_determinism_same_frames_same_bytes(tmp_path):
    a = V.produce(_frames(), tmp_path / 'a.mp4', fps=24)
    b = V.produce(_frames(), tmp_path / 'b.mp4', fps=24)
    assert a['sha256'] == b['sha256']
    g = V.grade(tmp_path / 'a.mp4', tmp_path / 'b.mp4')
    assert g['reward'] == 1.0 and g['tokens_used'] == 0


def test_grade_rejects_different_content(tmp_path):
    V.produce(_frames(seed=0), tmp_path / 'a.mp4', fps=24)
    V.produce(_frames(seed=9), tmp_path / 'b.mp4', fps=24)
    g = V.grade(tmp_path / 'a.mp4', tmp_path / 'b.mp4')
    assert g['reward'] == 0.0


def test_grade_rejects_different_encoder_settings(tmp_path):
    """Encoder settings are part of the contract. Identical frames at a
    different bitrate are a different film."""
    V.produce(_frames(), tmp_path / 'a.mp4', fps=24, bitrate='6M')
    V.produce(_frames(), tmp_path / 'b.mp4', fps=24, bitrate='2M')
    g = V.grade(tmp_path / 'a.mp4', tmp_path / 'b.mp4')
    assert g['reward'] == 0.0


def test_receipt_doi_is_the_delivered_bytes(good):
    d, r = good
    rec = V.receipt(d / 'good.mp4')
    import hashlib
    assert rec['sha256'] == hashlib.sha256((d / 'good.mp4').read_bytes()).hexdigest()
    assert rec['citation'] == 'æ://film/good'
    assert rec['ok'] is True


def test_gate_on_missing_file_refuses(tmp_path):
    g = V.gate(tmp_path / 'nope.mp4')
    assert g['ok'] is False and 'not found' in g['reason']


def test_produce_with_no_frames_refuses(tmp_path):
    r = V.produce([], tmp_path / 'empty.mp4')
    assert r['ok'] is False and 'no frames' in r['reason']


def test_thresholds_are_the_published_ones():
    """Guard against the temptation to lower a threshold to make a film pass."""
    assert (V.LUM_MIN, V.CON_MIN, V.MOV_MIN, V.BLACK_MAX_PCT) == (20.0, 10.0, 0.5, 5.0)
    assert V.MUX_TOLERANCE_S == 0.15
