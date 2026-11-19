# tinyGPU

**A complete deterministic GPU robot renderer in 527 lines.**
Real CAD · 1,007,041 triangles a frame · two pip installs · zero build dependency.

```bash
pip install cupy-cuda13x pillow numpy      # ffmpeg on PATH

tinygpu doctor                 # measures your card, proves compute
tinygpu fetch                  # Menlo's Asimov CAD, hash-verified
tinygpu render out.mp4         # a film, on your card, no cloud
tinygpu verify out.mp4         # decode + geometry + sha256
```

No compiler. No C++. No engine. No vendored binaries. No graphics context.
No credentials. No account. No network at render time.

---

## Three efforts, one route

This exists because two organisations published work a laptop can consume, and
a third idea says they should be reachable by anyone.

| | |
|---|---|
| **Menlo Research** | authored the Asimov-1 humanoid — 26 CAD links, 25 joints, every mesh open |
| **Nous Research** | authored Hermes Agent — the runtime that carries intent and receipts |
| **#opensourceware** | the claim that open capability composes *downward*, to one person with a laptop |

tinyGPU is the third made concrete. It vendors none of Menlo's CAD and requires
none of Nous' runtime. It is the small route between them.

**No institutional endorsement is claimed.** See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

## What is actually new

**Not the rendering technique.** This is a z-buffer software rasteriser with
flat per-triangle normals and two directional lights — 1990s graphics. No PBR,
no shadows, no BVH, no anti-aliasing.

Three things are rare together:

**1. The dependency floor.** GPU robot rendering normally requires Isaac Sim,
Unity, Unreal, a CUDA toolchain, or at minimum an EGL/OpenGL context. This
requires `pip install cupy` and ffmpeg. **22.6 KB of code.**

**2. Determinism on a GPU.** Most GPU pipelines are not reproducible — float
ordering, atomic races, driver variance. The depth pass packs depth and triangle
id into one `uint64` and resolves visibility with a single `atomicMin`, so there
is no read-modify-write race. Measured: **12/12 frames byte-identical** across
independent runs. A stranger gets your exact pixels, not approximately your
pixels. That is what makes a receipt mean something.

**3. Headless GPU without a graphics stack.** On an Optimus laptop the NVIDIA
OpenGL ICD is often unregistered, so MuJoCo's GL silently falls back to the Intel
iGPU. EGL is unavailable on Windows. CuPy `RawKernel` bypasses the graphics API
entirely — no display server, no window, no context.

> **Not a new rendering technique. A new dependency floor.**

---

## Measured

Full detail in [RESULTS.md](RESULTS.md). RTX 3050 6GB Laptop — **~6.0 TFLOPS,
about 0.6% of an H100**:

```
device       cc 8.6 · 20 SMs · 1.18 GHz · 6.44 GB
matmul       21.51 ms · 798.7 GFLOPS   (doctor proves compute, not enumeration)
geometry     26 links · 25 joints · 1,007,041 triangles/frame
raster       71.6 ms/frame
600 frames   217.6 s wall  (~3.6 min per minute of 9:16 film)
gate         PASS · lum 26.8 · contrast 51.49 · motion 3.643 · black 0
audio        48.55 s · 0.0% near-silent · 20 world events
tests        15 passed in 2.38 s
```

Against the other two paths on the **same card**:

| Path | Raster/frame | |
|---|---|---|
| MuJoCo GL on Intel UHD | ~570 ms | the accidental default |
| **tinyGPU** (CuPy CUDA) | **71.6 ms** | 8x faster, deterministic, portable |
| WebGL ANGLE->D3D11 | ~2 ms | **36x faster than tinyGPU**, with shadows |

The fastest path is not this one. This one is the one a stranger can run.

---

## The sibling

| | tiny-voca | tinyGPU |
|---|---|---|
| weight | 4.5M params · 57 MB | **527 lines · 22.6 KB** |
| runs on | CPU | your NVIDIA card |
| deps | onnxruntime | cupy, pillow, numpy |
| cloud | none | none |
| account | none | none |
| compiler | none | none |

tinyGPU vendors **no CAD**. `fetch` pulls Menlo Research's meshes from their
public repo and writes a SHA-256 manifest. Duplicating 100 MB of someone else's
work would drift from it.

## Honesty

- **Simulation only.** No physical robot is attached.
- A pose trace is **not a signed command**. Nothing here grants authority.
- `doctor` measures your machine; it does not assume. If CUDA is missing it
  says so and names the fix.
- `verify` reports decode and geometry. It does **not** judge visual quality.
- CAD authored by **Menlo Research**. No institutional endorsement is claimed.

## Four bugs worth knowing

Each was the same class — inventing an API instead of reading it:

1. The renderer class is `RtxRenderer`, not `Raster`.
2. `urdf.json` uses `links[name]['mesh']`, and `joints` is a **list**, not a dict.
3. A loop variable named `n` shadowed the normals array. Twice.
4. The shade kernel wants colours in **0–1**. Passing 0–255 saturates every
   pixel to white — producing a *valid MP4 with correct geometry* that looks
   like a flat silhouette, and the luminance gate passed it.

There is now a regression test for #4.

**A passing pipeline is not a right picture.** Look at the frame.

## Governed by design

tinyGPU draws. It does not act. A pose trace is **not a signed command**. Nothing
here grants authority, opens a socket, or moves a physical device. The policy
layer — `allow`, `require_approval`, `deny`, with cited rules and SHA-256
receipts — lives in the æ stack: **https://myaelmendez.github.io/refusal.html**

> Every robotics platform ships capability and leaves authority as an exercise.
> The refusal has to belong to the person who owns the robot.

## Development

```bash
pip install -e ".[cuda,dev]"
pytest -q                      # 15 tests, ~2.4 s
```

GPU tests skip cleanly without CUDA rather than silently passing. Each test maps
to a claim above, including a regression guard for the colour-range bug.

## License

Apache-2.0 · `HUMAN://ROOT` · `>_æ://` · [@yaelmendez](https://x.com/yaelmendez)
