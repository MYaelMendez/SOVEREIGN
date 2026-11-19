# Third-party notices

tinyGPU is a small route to other people's large work. That is the whole point,
and it is stated rather than implied. **No institutional endorsement is claimed
from Nous Research, Menlo Research, or NVIDIA.**

---

## Menlo Research — the robot

The Asimov-1 humanoid CAD is authored and published by **Menlo Research**.
tinyGPU vendors **none** of it: `tinygpu fetch` downloads the URDF and 26 STL
meshes from their public repository at run time and writes a SHA-256 manifest.

- https://github.com/menloresearch/asimov-1
- `sim-model/asimov_1_25dof/` — `urdf.json`, `asimov_1_25dof.urdf`, `meshes/*.STL`
- https://docs.menlo.ai/asimov/1/overview

Please consult the upstream repository for the licence governing the CAD assets.
They are fetched, not redistributed here.

Menlo's `AGENTS.md` states that the guard belongs in user code. tinyGPU draws;
it does not act. The policy layer that governs motion lives in the æ stack, not
in this renderer.

---

## Nous Research — the runtime

**Hermes Agent** (Nous Research) is the agent runtime that carries intent and
orchestrates the pipeline this renderer plugs into. tinyGPU does not depend on
Hermes to run — it is a standalone CLI — but the films, the receipts, and the
governed tool surface are produced through it.

- https://github.com/NousResearch/Hermes-Agent
- https://hermes-agent.nousresearch.com/docs

The `HERMES_HOME` environment variable is read only to locate optional tooling
(ffmpeg, the TTS model). Nothing is required from it.

---

## MuJoCo — physics (not used by the render path)

MuJoCo is Apache-2.0, Copyright DeepMind Technologies Limited.
https://github.com/google-deepmind/mujoco

tinyGPU's renderer does **not** import MuJoCo. Forward kinematics is computed
directly from the URDF tree. MuJoCo is used elsewhere in the æ stack for physics
and for the Menlo locomotion policy; it is listed here because the geometry
pipeline is often paired with it and readers should not assume a dependency.

---

## CuPy — the GPU array library

CuPy is MIT-licensed, Copyright Preferred Networks, Inc. and contributors.
https://github.com/cupy/cupy

The CUDA kernels in `rtx_raster.py` are original to this project and compiled at
run time through `cupy.RawKernel`. No CuPy source is vendored.

---

## NumPy · Pillow

- NumPy — BSD-3-Clause, https://github.com/numpy/numpy
- Pillow — MIT-CMU, https://github.com/python-pillow/Pillow

---

## FFmpeg

FFmpeg is invoked as an external binary for encoding (`h264_nvenc`). It is
**not** vendored or linked. The build used here is FFmpeg 7.1, chosen because
driver 610.91 exposes NVENC API 13.0 and FFmpeg 9.x requires 13.1.

- https://ffmpeg.org — LGPL/GPL depending on build configuration
- Users must supply their own FFmpeg and honour its licence.

---

## NVIDIA CUDA

CUDA and NVENC are proprietary NVIDIA technologies used through their public
APIs. No NVIDIA source, headers, or binaries are redistributed.

---

## The æ stack

The policy gate, the receipt chain, the sound world, and the film harnesses are
part of the æ / #opensourceware stack by Yæl Méndez, Apache-2.0.

- https://github.com/MYaelMendez
- https://myaelmendez.github.io/refusal.html

The sound-world stage optionally uses an Apache-2.0 DSP path derived from
`stdevMac/orb-audio`. Its non-commercial `detail` model is **never loaded**.

---

## Summary of what is original here

| Component | Origin |
|---|---|
| `rtx_raster.py` — CUDA depth/shade kernels, uint64 packed visibility | **original** |
| `tinygpu.py` — URDF FK, STL loader, CLI, doctor/fetch/verify | **original** |
| Determinism construction and its test | **original** |
| Asimov CAD | Menlo Research, fetched |
| Agent runtime | Nous Research, optional |
| Array math, imaging, encoding | CuPy, NumPy, Pillow, FFmpeg |
