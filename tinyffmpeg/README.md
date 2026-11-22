# tinyffmpeg

A sovereign instrument for the local FFmpeg builds. Apache-2.0 · one file · stdlib only.

**tinyffmpeg does not build FFmpeg and does not replace it.** It governs the
builds already on the machine: it finds them, **proves** them, exposes their
capabilities, encodes with a SHA-256 receipt, and grades determinism by running
twice.

The family: `tinycuda` (pixels) · `tinygpu` (robots) · `tinymujoco` (motion) ·
`tinycan` (the bus) · `tinycudavideo` (the seam) · `tinyfilmmemory` (the ledger)
· `tinypython` (the policy) · `tinyonnx` (the oracle) · `tinyvision` ·
`tinyffmpeg` (the codec bridge).

## When to use

- You need to know which FFmpeg builds exist here and whether they actually work.
- You are about to encode and want a receipt you can verify.
- You need to prove a render is reproducible rather than assert it.
- A sibling tool claimed "GPU encode" and you want the measurement, not the claim.

## Shape

```
tinyffmpeg/
  tinyffmpeg.py          the instrument: doctor() + verbs + refusals + ledger
  tests/test_tinyffmpeg.py   pins the REFUSALS on real fixtures
  README.md · RESULTS.md · pyproject.toml · LICENSE
```

## Four invariants

1. **`doctor()` returns `ok` only from what it measured** — it runs a real
   one-frame encode. A binary that lists encoders but cannot encode is reported
   as `REFUSED`, never as a build.
2. **Every verb has a refusal path** — missing input, unknown codec, absent
   binary, empty output. The tests pin each refusal.
3. **The contract is read from the artifact** — the encoder list from the
   binary's own `-encoders` output, the receipt from the output bytes.
4. **A receipt is a claim until re-run** — `grade()` encodes twice and compares
   SHA-256. Two agreeing hashes are the evidence; one run is not.

## Use

```bash
python tinyffmpeg.py doctor          # every build, proven by a real encode
python tinyffmpeg.py probe           # encoders / decoders / filters / nvenc
python tinyffmpeg.py encode in.mp4 out.mp4 --codec libx264
python tinyffmpeg.py grade in.mp4    # determinism: two runs, byte-compared
python tinyffmpeg.py ledger          # hash-chain integrity
```

Tests:

```bash
python -m unittest tests.test_tinyffmpeg -v
```

## Measured on this machine

See `RESULTS.md`. Every number there was produced by `doctor`/`probe`/`grade` on
this host — nothing projected, nothing copied from a README.

## Limits (a capability claim without its limit is marketing)

- **NVENC determinism is not guaranteed.** `grade()` compares bytes; a mismatch
  is reported as a FINDING, not hidden. Hardware encoders may legitimately vary
  run-to-run with driver state.
- **Three builds are probed, not one.** They disagree: 7.1.5 lacks `av1_nvenc`,
  9.0.1 and 8.1.2 have it. A capability claim must name the build.
- **No build is performed.** If the build you want is absent, `doctor()` says so;
  it never downloads or compiles anything.
- **`-filters`/`-encoders` column parsing is flag-driven.** A build with a new
  flag column will parse as fewer entries rather than as wrong ones — re-probe
  after upgrading.

## Ledger

`C:\æ\logs\tinyffmpeg.jsonl` (override `TINYFFMPEG_LEDGER`). Append-only,
hash-chained, records DECISIONS (doctor/probe/encode/grade), never intent.

---

*#opensourceware · measured, not declared · the codec bridge*
