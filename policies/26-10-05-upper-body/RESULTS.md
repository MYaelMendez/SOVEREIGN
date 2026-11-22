# Measured — Menlo/asimov1-locomotion-26-10-05-upper-body

Every number below was produced on this machine by `measure.py`, then
recomputed independently by `verify_trace.py` from the trace geometry (not from
the trace's own success flag). Simulation only — `grants:false`, `executed:false`.

## Machine

```
Host    Victus · Windows 11 · git-bash
CPU     Intel i5-13420H · 12 threads
Python  C:/gpu/Scripts/python.exe · MuJoCo 4.0.1 · ONNX Runtime · NumPy
GPU     RTX 3050 — NOT USED (CPU walk)
```

## Policy

```
repo      Menlo/asimov1-locomotion-26-10-05-upper-body
policy.onnx   827,578 bytes
sha256    b1dc57328e0e5bbc767ba072e37341edba39dca4127bf918f415f6375b6b4f65
input     obs      [1, 78] float32
output    actions  [1, 12] float32   ← 12 leg joints only, NOT 23
trained   model_9500.pt · run 2026-10-05_17-24-12_upperik_new_ankle · Isaac Lab PPO+AMP
```

## This policy is a DIFFERENT contract from the pinned 0818 harness

The stock `tinypython.py walk()` targets the 0818 model (23 actions, uniform 0.25
scale). Running this checkpoint through it would feed 12 actions into a 23-wide
slot and report garbage. `measure.py` mirrors the harness's PD loop, observation
recipe and command logic exactly, and overrides only what this checkpoint's own
ONNX metadata specifies:

| term | 0818 harness | this policy (from ONNX metadata) |
|---|---|---|
| actions | 23 (all joints) | **12** (legs only; waist+arms held at default) |
| action scale | 0.25 uniform | 0.25, **ankle-roll 0.08** |
| ankle target clip | none | **ankle-roll ±0.09 rad** |
| ankle-pitch kp/kd | 110 / 5 | **224.42 / 10.201** |
| ankle-roll kp/kd | 110 / 5 | **35.2 / 1.6** |
| prev-action obs | 23 | 12 leg actions + 11 zeros = 23 |

Observation layout (78) matches `env.yaml` and the harness `SLOTS` exactly:
angvel×0.25 · projected gravity · [vx,vy,wz] · 3 joint-pos slots · 3 joint-vel
slots×0.1 · prev action. Control: 0.02 s period, 4 substeps of 0.005 s, lag 2,
one-pole α=0.992105. Physics MJCF = pinned `asimov_1_policy_physics.xml`
(`nq=30`, `nv=29`).

## Reference walk — 12 s @ vx 0.4

```
policy ticks     600
physics steps    2400
travel x         +4.4389 m     (measured speed 0.370 m/s vs 0.4 commanded)
travel y         +0.2133 m
COM travel x     +4.4241 m
min base height  0.612 m
fall             none
heading drift    −6.2°
wall             1.60 s   → 7.48× realtime
trace sha256     048ff0b36a8288cf855f0477ce8fa7c15ab9d3951eac847e50a902d36179d88e
```

## Command space (8 s runs) — all six verified

| command | x (m) | y (m) | min_z | upright | obeyed | L knee | R knee |
|---|---|---|---|---|---|---|---|
| stand (0,0,0) | −0.007 | +0.004 | 0.609 | ✓ | ✓ | 2.7° | 2.8° |
| walk vx 0.4 | +4.439 | +0.213 | 0.612 | ✓ | ✓ | 41.7° | 41.7° |
| fast vx 0.6 | +4.659 | +0.598 | 0.611 | ✓ | ✓ | 56.8° | 61.7° |
| back vx −0.2 | −0.917 | +0.046 | 0.609 | ✓ | ✓ | 6.9° | 6.0° |
| turn wz 0.5 | −0.020 | +0.033 | 0.610 | ✓ | ✓ | 5.5° | 6.9° |
| strafe vy 0.3 | +0.093 | +1.482 | 0.611 | ✓ | ✓ | 8.1° | 13.6° |
| strafe vy −0.3 | +0.272 | −1.204 | 0.610 | ✓ | ✓ | 14.8° | 9.4° |

(12 s for the vx 0.4 reference; 8 s for the rest.)

## The gait, measured (12 s @ vx 0.4)

```
foot separation     min 0.204 · max 0.290 · mean 0.247 m
left knee swing     41.7°
right knee swing    41.7°      ← symmetric, unlike 0818's asymmetric shuffle
foot z spread       0.073 m    ← feet clear the ground ~7 cm
approx cycle        ~0.41 s    (from foot-separation crossings)
```

Compared with the pinned 0818 policy (shuffle, 1.5 cm foot clearance, asymmetric
knees), this upper-body-control checkpoint walks **faster and cleaner**: higher
foot clearance, near-symmetric knee swing, and a small heading drift under a
pure-forward command.

## Determinism

Same command → identical trace bytes. Two 4 s vx 0.4 runs:
`3901c4c24ec87428faa1bef5d292ce9d444dd1178818a6417bb333c7ba59a872` (both).

## Limits, stated

- **Simulation only.** No hardware attached; no socket, serial, or motor addressed.
- **Upper body held at default.** The policy controls 12 leg joints; the real
  deployment supplies independent waist/arm position targets randomized in
  training. This run holds them at the default pose (PD), so it is a
  locomotion-floor measurement, not the trained upper-body behavior.
- **Training randomizations not reproduced** (noise, delays, gain jitter). The
  inference contract is matched exactly; the robustness envelope is not.
- **One machine.** No second-box reproduction.
- Requires the pinned physics MJCF (`nq=30`, `nv=29`).
