# Menlo `asimov1-locomotion-26-09-24` — measured through tinyPython

Policy pulled from https://huggingface.co/Menlo/asimov1-locomotion-26-09-24
into this directory. Measured with the local harness
`C:/æ/tinypython/tinypython.py` (verbs `doctor`, `walk`, `verify`) against the
pinned physics MJCF. No git push. No hardware. Simulation only.

## Artifact

| file | bytes | sha256 |
|---|---|---|
| `policy/policy.onnx` | 833,942 | `27754387464c8df363f099b8742978f40750a99d3420e80757207d7e8d099067` |
| `policy/policy.pt` | 843,734 | `b1c4ea1e1b9b04574cd69782f3563b87ea3af09b8c159781afd55babf88e6946` |
| `env.yaml` | 60,279 | `a995ab48ec17708a17e9069a7317366d2298199009a4ec7fc481775bbce873a5` |
| `agent.yaml` | 2,823 | `5b1562c3e5fe5dafee7cd050b0058b21767d0e1beee46b4bd7d11a19f6aefcfb` |
| `model/asimov_1_policy_physics.xml` | 25,759 | pinned (copied from ae-locomotion 1.0.0) |

`doctor`: ok — onnxruntime 1.32.0 · mujoco 4.0.1 · `gpu_required: false`.

## Reference run — 12.0 s @ vx 0.4

| metric | value |
|---|---|
| policy ticks / physics steps | 600 / 2400 |
| base travel x | **+4.6405 m** |
| COM travel x | +4.6234 m |
| mean forward speed | 0.3867 m/s (commanded 0.4) |
| min base height | **0.6111 m** |
| fall | none |
| upright / obeyed command | true / true |
| trace sha256 | `32a30a7f8a875bd4b120eebde76153a628475e6279e6aa3a5c061e2cd102282d` |

Determinism: a second identical run produced the same trace SHA-256.
Warm wall time 1.43 s (8.4× realtime); the first cold run took 24.4 s.

## Command space (8.0 s each, all ok, no fall)

| command | x (m) | y (m) | min z (m) | foot sep mean (m) | knee swing L/R (deg) |
|---|---|---|---|---|---|
| stand (0,0,0) | +0.041 | +0.009 | 0.6101 | 0.2143 | 3.3 / 2.9 |
| walk vx 0.4 | +3.057 | +0.008 | 0.6111 | 0.2406 | 40.2 / 39.9 |
| fast vx 0.6 | +4.395 | −0.040 | 0.6062 | 0.2556 | 46.4 / 56.5 |
| turn wz 0.5 | +0.381 | +0.432 | 0.6104 | 0.2187 | 11.6 / 10.0 |
| back vx −0.2 | −1.028 | −0.042 | 0.6090 | 0.2259 | 10.9 / 8.7 |
| strafe vy 0.3 | +0.344 | +1.768 | 0.6108 | 0.2247 | 21.7 / 16.2 |
| strafe vy −0.3 | +0.547 | −1.978 | 0.6099 | 0.2232 | 20.3 / 20.6 |

Gait metrics recomputed from each trace by MuJoCo FK (`measure.py`); full data in
`measure_report.json`.

## The gait, measured (12 s @ vx 0.4)

```
foot separation    min 0.197 · max 0.279 · mean 0.241 m
left knee          11.3° → 51.5°   (40.2° swing)
right knee       −52.7° → −12.8°   (39.9° swing)
foot z at peak     −0.530 / −0.529 m relative to base
                   (abs 0.095 / 0.099 m; ~6.5 cm above the 0.030 m floor)
```

Still a grounded shuffle, but the ankle-update checkpoint lifts the feet higher
than the 0818 policy (foot-z-at-peak −0.565/−0.580 relative to base), i.e. ~3–5 cm
more clearance.

## Contract caveat — read before trusting the ankle numbers

The harness is hardcoded to the **0818** inference contract. This checkpoint's
`env.yaml` changes the ankles, and the harness does not apply those changes:

| joint | harness kp / kd / effort | env.yaml 26-09-24 kp / kd / effort | harness scale | env.yaml scale |
|---|---|---|---|---|
| ankle_pitch | 110 / 5 / 40 | **224.42 / 10.201 / 72** | 0.25 | 0.25 |
| ankle_roll | 110 / 5 / 17 | **35.2 / 1.6 / 18** | 0.25 | **0.08** + clip [−0.09, 0.09] |

All other joints match exactly (hip/knee 150/5, waist 65/5, shoulder 57-96/5,
elbow/wrist 40/2; effort limits identical). Observation order (78), action order
(23), default pose, 50 Hz policy / 200 Hz physics and the 2-substep lag also match.

So the numbers above are the policy measured through the harness's **legacy
ankle contract**, not the checkpoint's native ankle settings. The policy still
walks and obeys every command, but a native-contract run (ankle-roll scale 0.08,
ankle target clip, ankle PD 224.42/10.201 and 35.2/1.6) has **not** been measured
— the harness has no code path for it. That check is missing, not passed.
