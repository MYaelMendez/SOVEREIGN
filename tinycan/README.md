# tinyCAN

**The bus between the decision and the body.** Stdlib only. Deterministic. Gradeable.

Every other member of the tiny family assumes a command reaches its motor
instantly. On the real Asimov-1 it does not.

```bash
python tinycan.py doctor
python tinycan.py compare
python tinycan.py poll --mode rows
```

## The topology is theirs

Read from Menlo Research's engineering slide, *"Where every frame goes in one
5 ms tick"*:

```
RPU        Radxa CM5 · firmware 200 Hz · one tick = 5,000 µs
motors     25 on 5 buses
chips      6 × MCP2518FD CAN-FD, one per bus (5 motor buses + battery)
SPI        spi4 ← right arm + left arm
           spi0 ← waist/neck + left leg
           spi1 ← right leg + battery
```

## The constants are a MODEL

Menlo published three numbers: the sequential poll ends at **4,366 µs**, and at
1.67 ms the sequential firmware has read **8/25** replies while the PIO burst has
read **15/25**. They did not publish per-frame SPI or CAN timings.

The per-frame constants here were fitted to those three points by grid search
plus local refinement:

```
rows@1.67ms    8/25   EXACT
burst@1.67ms  15/25   EXACT
aggregate    4,836 µs vs 4,366 µs published   (+10.8%)
```

**The residual is declared in every result.** The model is *conservative* — it
over-estimates the poll, so a policy that fits here has margin on their hardware.
`fit_quality` travels with the output so nobody mistakes a fitted model for a
measurement of their firmware.

One modelling error worth recording: the first burst model dispatched every
transfer at t=0 and predicted 22/25. **A burst is not free** — the RPU still pays
a per-transfer issue cost. Adding `BURST_DISPATCH_US` brought it to exactly 15.

## What is real regardless of the constants

The contention rules are physical, and there is a test for each:

- one frame per bus at a time
- two chips sharing an SPI port serialize
- no reply is read before it arrives
- every motor gets exactly one reply

## The finding

```
ROWS   4,836 µs · 96.7% of the tick ·  8/25 @1.67 ms
BURST  2,442 µs · 48.8% of the tick · 15/25 @1.67 ms
speedup 1.98× · headroom gained 2,394 µs
```

**Sequential firmware consumes 96.7% of the tick before the controller thinks.**
A policy tuned in a simulator that delivers commands instantly is tuned against
a robot that does not exist. This is a sim-to-real gap no gait tuning closes.

## Grading

```python
grade(ref, cand) → reward 1.0 / 0.0 · tokens_used 0
```

It hashes the **event trace**, not the summary. Two polls with the same end time
but different ordering are different polls, and grade 0.0.

## Tests

```bash
python -m pytest tests/ -q     # 18 passed
```

Guards the topology, the four physical contention rules, causality, determinism,
the two published throughput points, and that the residual stays declared.

## Not verified

- No second-machine reproduction.
- The constants are fitted, not measured on Menlo hardware.
- 25 motors on the bus vs 23 actuators in the policy model — unresolved.

## Licence

Apache-2.0. Topology facts from Menlo Research's public engineering material.
Asimov-1 hardware is CERN-OHL-S-2.0; this module redistributes no CAD.

`>_æ://` · HUMAN://ROOT · grants false
