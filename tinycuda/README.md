# tinyCUDA

**A deterministic GPU triangle rasteriser in one file.**
Any triangles. One dependency. No OpenGL, no context, no compiler.

```bash
pip install cupy-cuda13x numpy

tinycuda doctor                      # compiles AND runs the kernels
tinycuda bench                       # throughput across triangle counts
tinycuda render mesh.stl out.png
tinycuda render tris.npz out.png --width 1080 --height 1920
```

```python
from tinycuda import Raster, persp, look_at, fit_camera

r = Raster(720, 1280)
mvp, centre, radius = fit_camera(verts)
pixels = r.render(verts, norms, colours, mvp)   # uint8 H×W×3, deterministic
```

No robot. No CAD. No scene graph. Triangles in, pixels out.

---

## Measured — RTX 3050 6GB Laptop, 720×1280

```
   1,000 triangles    2.49 ms    402 fps     0.40 Mtri/s
  10,000 triangles    2.55 ms    393 fps     3.93 Mtri/s
 100,000 triangles    4.22 ms    237 fps    23.72 Mtri/s
1,000,000 triangles   20.45 ms     49 fps    48.91 Mtri/s
```

**49 fps at a million triangles** on a card with ~6 TFLOPS — roughly 0.6% of
an H100.

Note the shape of the curve: 1k → 10k is flat. **The per-pixel shade pass
dominates at low triangle counts**; geometry only starts to matter past 100k.
That is a real property of a two-pass rasteriser, and there is a test pinning
it rather than pretending the cost scales with triangles.

---

## Why it is deterministic

Most GPU pipelines are not reproducible — float ordering, atomic races, driver
variance. The usual construction is a race:

```
if (z < zbuf[pixel]) { zbuf[pixel] = z; colour[pixel] = c; }   // RACE
```

Two fragments can both pass the test and write out of order. Instead:

```
packed = (depth_bits << 32) | (triangle_id + 1)
atomicMin(&zid[pixel], packed)        // one atomic, one winner
// second pass shades from the winning id
```

**No read-modify-write window.** Positive floats order correctly as unsigned
ints, so the depth comparison is exact.

The empty-pixel sentinel is `0xFFFFFFFF00000000`, **not** all-ones: all-ones
would make the low bits read as triangle `0xFFFFFFFF` and index far past the
colour buffer.

Verified: 5 repeats and 2 fresh contexts, all byte-identical.

---

## Why it exists

On an Optimus laptop the NVIDIA OpenGL ICD is often **unregistered**, so every
GL path silently lands on the Intel iGPU. EGL is unavailable on Windows. Four
levers to force OpenGL onto the discrete card all failed.

CUDA is unaffected. So rasterise on the card directly — no display server, no
window, no graphics context.

**The capability was always there. Only the route was missing.**

---

## What it is not

**1990s technique.** Z-buffer, per-triangle flat normals, two directional
lights. No PBR, no shadows, no BVH, no anti-aliasing, no texture mapping.

A hardware rasteriser is **~36× faster on the same card**. This exists for
portability and determinism, not speed. Saying so is the point — a reviewer
who opens the shader finds the README already told them.

**Colours are 0–1 floats.** Passing 0–255 saturates every pixel to white,
producing a valid image with correct geometry that looks like a flat
silhouette. There is a test for this because it happened.

---

## The family

| | role | weight |
|---|---|---|
| [tiny-voca](https://github.com/MYaelMendez/tiny-voca) | voice | 4.5M params · 57 MB |
| **tinyCUDA** | **triangles → pixels** | **~300 lines** |
| [tinyGPU](https://github.com/MYaelMendez/tinyGPU) | robot renderer | 527 lines |
| [tinyPython](https://github.com/MYaelMendez/tinyPython) | motion from control | ~330 lines |

tinyGPU depends on this package. It used to carry its own copy of the kernels;
two copies drift, so the primitive was extracted.

All of it composes into **tinyASIMOV** — a robot that speaks, that you can see,
that moves under its own control, and that refuses you with a cited rule.

---

## Tests

```
15 passed in 1.32s
```

Determinism across repeats and fresh contexts · depth ordering (a near red
quad must occlude a far blue one) · empty scene safety · length-mismatch
refusal · resolution dominating cost · the colour-range regression · absence
of network or credential paths.

GPU tests skip cleanly without CUDA rather than silently passing.

---

Apache-2.0 · `HUMAN://ROOT` · `>_æ://` · [@yaelmendez](https://x.com/yaelmendez)
