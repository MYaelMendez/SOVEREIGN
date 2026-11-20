# RESULTS — measured on this machine

Host: Victus · i5-13420H · 32 GB · RTX 3050 6 GB Laptop · driver 610.91
CuPy 14.2.0 · CUDA runtime 13.2 · ffmpeg 7.1 NVENC (API 13.0) · Windows 11

## Gate over the corpus

| film | verdict | lum | motion | frozen tail | failed |
|---|---|---|---|---|---|
| `asimov-dao-916` | PASS | 20.67 | 4.311 | 0.003 s | — |
| `tinycan-916` | PASS | 26.39 | 0.908 | 0.0 s | — |
| `mobility-4d-916` | PASS | 20.9 | 1.313 | 0.0 s | — |
| `rtx-waetz-sound-916` | **FAIL** | 24.87 | 2.034 | 15.816 s | mux_match |
| `rtx-waetz-sound-916-fixed` | PASS | 23.81 | 3.64 | 0.0 s | — |
| `tinygpu-demo-916` | **FAIL** | 25.06 | 4.097 | 23.555 s | mux_match |
| `tinygpu-demo-916-fixed` | PASS | 23.99 | 4.66 | 0.013 s | — |

All measured at native 720×1280. The two live films failed on `mux_match`
alone — their pixels are fine, which is exactly why they shipped.

## Repairs

Both live defects repaired by decoding the picture to frames, extracting the
audio untouched, and re-encoding with picture looped to cover the speech:

```
rtx-waetz-sound-916   200 frames · loop ×3 · 24.167 s video / 24.149 s audio · PASS
tinygpu-demo-916      600 frames · loop ×2 · 48.542 s video / 48.555 s audio · PASS
```

## Determinism

Same frames, same settings, two independent runs → identical SHA-256
`892bcde33ca219c9…`, `grade` reward 1.0, zero tokens.

## Tests

```
14 passed in 27.60s
```

## Not verified

- No second-machine reproduction. Every number here is from this laptop.
- The repaired films are local; the defective originals are still published.
- `-stream_loop` on an mp4 input silently no-ops with `-c:a copy`; the frame
  path is the one that works and the one `produce()` uses.
