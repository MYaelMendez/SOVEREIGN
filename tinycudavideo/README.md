# tinyCUDAVIDEO

**GPU frames to a receipted film — or a refusal.**

One file. CuPy + NVENC. No cloud, no model calls, no tokens. The film layer of
the tiny family: `tinycuda` grades pixels, `tinymujoco` grades motion, `tinycan`
grades the bus. None of them made a film. This does, and it refuses to certify a
broken one.

```bash
pip install cupy-cuda13x pillow numpy      # cupy wheel matches your CUDA runtime
python tinycudavideo.py doctor
```

## Why it exists

A pixel gate cannot see a frozen tail. Every frame it samples is a real frame;
the defect is that the **picture stopped while the audio continued**.

Three published films carried this defect and every one returned `PASS`:

| film | picture | audio | frozen tail |
|---|---|---|---|
| `rtx-waetz-sound-916` | 8.333 s | 24.149 s | **15.816 s** |
| `tinygpu-demo-916` | 25.000 s | 48.555 s | **23.555 s** |
| `asimov-dao-916` (first encode) | 20.000 s | 58.336 s | **38.336 s** |

The cause was one line in a mux command:

```python
'-t', f'{max(want, adur):.3f}'   # duration = audio length
'-i', 'f%05d.png'                # but only `want` seconds of picture
```

ffmpeg holds the last frame for the remainder. The film reports `ok: true`.
Luminance, contrast, motion and black-frame counts all pass, because they are
measured on frames that exist.

**`gate()` here checks the mux as well as the pixels.** Those three films now
fail on `mux_match`, and `produce()` returns `refused: true` instead of a
receipt.

## Usage

```python
from tinycudavideo import produce, gate, receipt, grade

r = produce(frames, out='film.mp4', fps=24, audio='voice.wav')
if not r['ok']:
    print(r['reason'])          # never a receipt for a broken film
```

```bash
python tinycudavideo.py doctor
python tinycudavideo.py gate film.mp4
python tinycudavideo.py receipt film.mp4
python tinycudavideo.py grade a.mp4 b.mp4
python tinycudavideo.py produce --frames ./frames --out film.mp4 --audio voice.wav
```

`frames` is an iterable of `H×W×3` uint8 arrays, or a directory of PNGs.

## What it measures

```
pixels   luminance > 20 · contrast > 10 · motion > 0.5 · black frames < 5%
mux      |video_duration − audio_duration| ≤ 0.15 s
```

Thresholds are the SupervisorVideo contract and are **never lowered to make a
film pass**. `test_thresholds_are_the_published_ones` guards them.

### Analysis scale is part of the measurement

The thresholds were calibrated at **native resolution**. Measuring at 180×320
and applying them anyway is a mis-calibration, not a stricter gate — downscaling
averages away the fine detail that carries motion in a HUD-heavy film:

```
tinycan-916   motion 0.908 at 720×1280   ·   0.435 at 180×320
```

Native by default. `gate(path, scale=(w, h))` opts into a fast approximation,
and every result records `analysis_scale` so two instruments are never compared
silently. This module shipped with that bug and its own test caught it.

## Determinism

Same frames + same encoder settings → same bytes → same SHA-256.

```
grade(a, b) → reward 1.0 · tokens_used 0 · method byte_compare
```

Encoder settings are part of the contract: identical frames at `2M` vs `6M` are
different films and grade `0.0`. There is a test for that too.

The receipt's DOI is the hash of the **delivered bytes**, not of the source.

## Picture coverage

When speech runs longer than picture, `produce()` loops the frame sequence
(`-stream_loop` on the image demuxer) rather than freezing. A cyclic gait
continuing is honest; a frozen frame is not. The loop count is recorded.

Note: `-stream_loop` on an **mp4 input** silently no-ops with `-c:a copy` — the
output kept its original 200 frames. Decode to PNGs first. `produce()` does.

## Requirements

- NVIDIA GPU with NVENC (tested: RTX 3050 6 GB Laptop, driver 610.91)
- ffmpeg built against NVENC API your driver exposes. Driver 592.27 → API 13.0;
  ffmpeg 9.0.1 wants 13.1 and **fails**; 7.1 targets 13.0 and works. Set
  `TINYCUDAVIDEO_FFMPEG` to a bin directory to pin a build.
- CuPy matching your CUDA runtime (`cupy-cuda13x` for CUDA 13)
- numpy, pillow

`doctor()` probes all of it and reports honestly, including what is absent.

## Tests

```bash
python -m pytest tests/ -q
```

14 tests. The load-bearing one is `test_frozen_tail_is_rejected`: it constructs
the exact defect that shipped three times and asserts the gate refuses it while
the pixel checks pass.

## Licence

Apache-2.0. Part of the æ:// tiny family — sovereign, local, receipted.

`>_æ://` · HUMAN://ROOT · grants false
