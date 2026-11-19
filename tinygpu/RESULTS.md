# Results

Every number here was measured on the machine below. Nothing is projected,
estimated, or carried over from another system. Where a claim is unverified it
says so.

## Machine

```
Host      Victus (Windows 11, git-bash)
CPU       Intel i5-13420H · 8 cores (4P+4E) · 12 threads
RAM       32 GB
GPU       NVIDIA GeForce RTX 3050 6GB Laptop GPU
          compute capability 8.6 · 20 SMs · 1.18 GHz boost
          6.44 GB VRAM · ~6.0 TFLOPS FP32
Driver    610.91
Python    3.12.13 (C:/gpu)
CuPy      14.2.0 · CUDA 13
NumPy     2.2.6 · MuJoCo 4.0.1 (not used by the render path)
ffmpeg    7.1 (h264_nvenc)
```

For scale: an H100 is ~1000 TFLOPS FP32 and 80 GB. This card is roughly **0.6%
of the compute and 8% of the memory**.

`tinygpu doctor` measures this at runtime and proves compute with a matmul
rather than trusting device enumeration:

```
matmul 2048×2048 fp32   21.51 ms   798.7 GFLOPS
```

## Geometry

Source: `menloresearch/asimov-1`, `sim-model/asimov_1_25dof/`.

```
links       26
joints      25
triangles   1,007,041 per frame
meshes      26 STL files, SHA-256 manifest written by `fetch`
```

Every triangle of every link is drawn. **No decimation, no point sampling, no
collision proxies.** An earlier build rendered the actuated MJCF's `group=3`
collision capsules as the body; it looked plausible and was wrong. The URDF is
the authoritative source.

## Render throughput

| Run | Frames | Raster/frame | Total wall | Output |
|---|---|---|---|---|
| smoke | 12 | — | — | determinism probe |
| short | 96 | 76.0 ms | 39.9 s | 487,028 B |
| demo | 600 | 71.6 ms | 217.6 s | 13,169,266 B |

The 600-frame run includes voice synthesis and the sound-world stage; raster is
the GPU portion only. **~3.6 minutes of wall time per minute of 9:16 film.**

### Comparison against the other two paths on the same card

| Path | Raster/frame | Notes |
|---|---|---|
| MuJoCo GL on **Intel UHD** | ~570 ms | the accidental default — NVIDIA OpenGL ICD unregistered |
| **tinyGPU** (CuPy CUDA) | **71.6 ms** | zero build dependency, deterministic |
| WebGL via Chrome ANGLE→D3D11 | ~2 ms | hardware raster, shadows, PBR, MSAA |

**tinyGPU is ~8× faster than the accidental path and ~36× slower than the
hardware path.** It exists for portability and determinism, not speed. Stating
this plainly is the point: the contribution is the dependency floor, not the
frame rate.

## Determinism

The headline claim, tested rather than asserted.

```
two independent 12-frame renders
identical frames   12 / 12
differing          none
frame 0 sha256     b03512e3db620076166df5eea7ee0aa3…
```

`tests/test_tinygpu.py::test_render_is_deterministic` renders the same scene
three times in one process and asserts a single hash.

**Why it holds:** the depth pass packs depth and triangle id into one `uint64`
and resolves visibility with a single `atomicMin`. There is no separate
read-modify-write of a colour buffer, so there is no race. The empty-pixel
sentinel is `0xFFFFFFFF00000000` — an all-ones sentinel would make the low bits
read as triangle `0xFFFFFFFF` and index past the colour buffer.

## Gate

The 600-frame demo, measured by the SupervisorVideo gate (thresholds unchanged):

```
luminancia_media   26.8    (threshold > 20)
contraste_medio    51.49   (threshold > 10)
movimiento_medio    3.643  (threshold > 0.5)
frames_negros       0      (threshold < 5%)
calidad            PASS
receipt            c449057d08369aa94f237747c11bd8b8ab66b82ee26185cce2921446030c2c27
```

Audio, measured from the decoded stream:

```
duration            48.55 s
peak                0.938
rms                 0.1281
near-silent windows 0.0%
world events        20
torch               false   (DSP path only; the non-commercial detail model is never loaded)
```

## Tests

```
15 passed in 2.38s
```

Each test maps to a claim: the URDF schema, mesh completeness, FK orthonormality
and responsiveness, colour normalisation (the bug that passed every gate),
determinism, non-empty geometry, honest `doctor` reporting, and the absence of
network or credential access in the render path.

GPU tests **skip cleanly** when CUDA is absent rather than silently passing.

## Known limits

- **No shadows, no PBR, no anti-aliasing, no BVH.** Flat per-triangle normals,
  two directional lights. This is a z-buffer software rasteriser.
- **No face tablet.** The OpenGL harness draws an expression on the head; this
  path does not. The head is a plain block.
- **No floor plane.** The robot floats against a gradient void.
- **One machine.** No second-box reproduction has been performed. This is the
  largest unverified claim in the project.
- **Simulation only.** No physical robot is attached. A pose trace is not a
  signed command; nothing here grants authority.
- **Windows-only paths** for fonts and the ffmpeg discovery fallback. The render
  math is portable; the CLI's font lookup is not.

## Reproducing

```bash
pip install cupy-cuda13x pillow numpy
python tinygpu.py doctor
python tinygpu.py fetch
python tinygpu.py render out.mp4 --frames 96
python tinygpu.py verify out.mp4
pytest -q
```

Compare your `frame 0 sha256` against the value above. If it differs, something
in the model, the driver, or the kernel changed — and that is worth knowing
before you trust the film.
