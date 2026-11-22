# Results

Every number measured on this machine by `tinyffmpeg doctor` / `probe` / `grade`.
Nothing projected, nothing copied from a README.

## Machine

```
Host    teknium · Windows 11 · git-bash
CPU     12 threads
RAM     32 GB
GPU     NVIDIA RTX 3050 6GB (cc 8.6)
Python  3.11/3.14 (stdlib only)
```

## Builds found: 3

| build | version | encoders | decoders | filters | NVENC | encode proof |
|---|---|---:|---:|---:|---|---|
| ffmpeg-7.1-nvenc | n7.1.5-12-g1fdbca85aa-20260731 | 229 | — | — | h264_nvenc, hevc_nvenc | **PASS** |
| ffmpeg-9.0.1-win32-x64 | n9.0.1-11-ge47273f4d9-20260831 | 234 | — | — | av1_nvenc, h264_nvenc, hevc_nvenc | **PASS** |
| ffmpeg-8.1.2-full_build | 8.1.2-full_build-www.gyan.dev | 244 | — | — | av1_nvenc, h264_nvenc, hevc_nvenc | **PASS** |

The `encode_proof` column is the load-bearing one: each build was made to encode
a real one-frame `testsrc` with `libx264`. Enumeration alone would have reported
`ok` for a binary that cannot encode.

`probe` on the first build:

```
encoders  229
decoders  531
filters   352
nvenc     ['h264_nvenc', 'hevc_nvenc']
```

## Determinism

```
grade(testsrc 320x240@10, 10 frames, libx264)
  sha256_a  1a2da6c2fafa259d6abca14f87dcfedf221b1b52063423f8177929706fe3a192
  sha256_b  1a2da6c2fafa259d6abca14f87dcfedf221b1b52063423f8177929706fe3a192
  deterministic  true
```

Two runs, byte-compared. Software `libx264` agreed. **NVENC may not** — a mismatch
is a finding to report, not a failure to hide.

## Refusals verified

| refusal | pinned by |
|---|---|
| input missing | `test_encode_refuses_missing_input` |
| unknown codec | `test_encode_refuses_unknown_codec` |
| binary absent | `test_probe_refuses_without_build` |
| grade on missing input | `test_grade_refuses_missing_input` |
| tampered ledger | `test_tamper_is_detected` |

8/8 tests pass.

## Ledger

```
chain_ok  true
records   4
head      6e9740a163b5
```
