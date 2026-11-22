# Measured — Menlo/asimov1-locomotion-0818 (baseline)

Measured on this machine through `C:/æ/tinypython/tinypython.py`. Nothing projected.

## Assets

| asset | value |
|---|---|
| policy | `policy/policy.onnx` · 831,809 B |
| policy sha256 | `47f70691ecd5afda2933b2e6430d2375004c943552284172a2d7b28b84188a0c` |
| physics | `model/asimov_1_policy_physics.xml` (pinned) · 25,759 B |
| physics sha256 | `21e6c1cd98ac284c888e40131daffae8bf754086ddb06fcf1b3503883b5df3f4` |
| repo | https://huggingface.co/Menlo/asimov1-locomotion-0818 |
| runtime | MuJoCo 4.0.1 · ONNX Runtime 1.32.0 · NumPy 2.2.6 · CPU only |

`doctor` → `ok: true`, `gpu_required: false`.

## Baseline run — 12.0 s @ vx 0.4 (the reference reproduction)

Trace `walk_12s_vx0.4.json` · receipt sha256
`43d4f0063128b3bd19eaf9df4875012062e9863d26f8f4080d17f82581f1bc9e`

| metric | measured |
|---|---|
| duration | 12.0 s |
| policy ticks | 600 |
| physics steps | 2400 |
| base travel x | **+4.1868 m** |
| COM travel x | +4.1743 m |
| lateral drift y | −0.6724 m |
| min base height | 0.6125 m (tick-level) |
| fall | none |
| success / verify | true / true (verify recomputes from geometry) |
| forward speed | 0.349 m/s (commanded 0.4) |
| wall / realtime | 21.53 s / 0.56× (machine under heavy concurrent load) |

Determinism: a second identical run produced byte-identical trace
(same sha256 `43d4f006…`).

## Gait, measured (12 s trace, 288 frames @ 24 fps)

```
foot separation     min 0.215 · max 0.328 · mean 0.300 m
left knee           7.6° → 46.4°   (38.8° swing)
right knee        −48.2° → −10.5°  (37.7° swing)
foot clearance      left 4.96 cm · right 4.68 cm above ground
foot z rel pelvis   −0.580 / −0.580 at peak  (0.1 cm difference)
cadence             ~1.54 steps/s
base z              mean 0.6244 m
```

## Gait character reproduction — 8.0 s @ vx 0.45

Trace `walk_8s_vx0.45.json` — reproduces the harness's documented finding
(`RESULTS.md`):

```
base travel         +3.1382 m · min_z 0.6106 m · no fall
left knee           6.6° → 52.5°   (45.9° swing)
right knee        −51.4° → −9.7°   (41.6° swing)
foot separation     min 0.215 · max 0.338 · mean 0.304 m
foot z rel pelvis   −0.569 / −0.575 at peak
clearance           left 5.9 cm · right 5.2 cm
```

**Verdict: a shuffle, not a stride.** Knees flex substantially but the feet
stay within ~5–6 cm of the ground and slide forward. Matches the documented
gait (knee swing 45.9°/41.7°).

## Limits

- Simulation trace only. `grants: false`, `executed: false`, `hardware: false`.
- The policy is Menlo's; it was run, not trained.
- Training randomizations (noise, delays, gain jitter) are not reproduced.
- Gait numbers are command-dependent: the 12 s vx 0.4 baseline shows smaller
  knee swing than the 8 s vx 0.45 character run.
