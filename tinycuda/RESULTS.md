# Results

Every number measured on this machine. Nothing projected.

## Machine

```
Host    Victus · Windows 11 · git-bash
CPU     Intel i5-13420H · 12 threads
RAM     32 GB
GPU     NVIDIA GeForce RTX 3050 6GB Laptop GPU
        cc 8.6 · 20 SMs · 1.18 GHz · 6.44 GB · ~6.0 TFLOPS FP32
Python  3.12.13 · CuPy 14.2.0 (CUDA 13) · NumPy 2.2.6
```

`doctor` proves compute rather than trusting enumeration:

```
matmul 1024² fp32   10.17 ms   211.2 GFLOPS
kernels             compiled and ran
opengl_required     false
```

The kernel check matters: a device that enumerates but cannot JIT is not
usable, and enumeration alone would report `ok`.

## Throughput — 720×1280, 4 reps, warmup discarded

| triangles | ms/frame | fps | Mtri/s |
|---|---|---|---|
| 1,000 | 2.49 | 402.0 | 0.40 |
| 10,000 | 2.55 | 392.8 | 3.93 |
| 100,000 | 4.22 | 237.2 | 23.72 |
| 1,000,000 | 20.45 | 48.9 | 48.91 |

**The curve is flat from 1k to 10k.** At low triangle counts the per-pixel
shade pass dominates; geometry cost only emerges past 100k. A test pins this
rather than asserting a scaling shape the rasteriser does not have.

Resolution is the stronger cost driver — verified 120×160 vs 480×640 at a
fixed 10k triangles.

## Determinism

```
5 repeats, one context      byte-identical
2 fresh Raster instances    byte-identical
```

Construction: depth and triangle id packed into one `uint64`, resolved with a
single `atomicMin`, shaded in a second pass from the winning id. No
read-modify-write window exists.

Empty-pixel sentinel `0xFFFFFFFF00000000`. An all-ones sentinel would make the
low bits read as triangle `0xFFFFFFFF` and index past the colour buffer —
this was a real crash during development.

## Correctness

`test_depth_order_is_correct` renders a near red quad over a far blue quad and
asserts the centre pixel is red. That is the property the packed atomic buys,
tested directly rather than inferred from a hash.

`test_empty_scene_is_background_not_garbage` renders zero triangles and asserts
a smooth gradient — the sentinel path is exercised, not assumed.

## Tests

```
15 passed in 1.32s
```

## Downstream

tinyGPU depends on this package (via a compatibility shim, `rtx_raster.py`).
After the refactor its own 15 tests still pass and it still renders:

```
1,007,041 triangles · 47.0 ms raster · 12 frames · ok
```

The full robot film measured through tinyGPU:

```
1712 frames · 71.33 s · raster 30.1 ms/frame
gate PASS · receipt 13d1b8b2d3250cb5e11058e9c54c368a0cba52e25418c82f189e7ce1fcd9f37b
```

## Limits

- No PBR, shadows, BVH, anti-aliasing, or texture mapping.
- Flat per-triangle normals — no smooth shading across a mesh.
- **~36× slower than the hardware WebGL path on the same card.**
- Binary STL only; ASCII STL is not supported.
- One machine; no second-box reproduction.
- Windows was the development host; the render math is portable but the CLI
  has not been exercised on Linux or macOS.
