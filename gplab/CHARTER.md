# The Governance-and-Provenance Laboratory

**Handle:** GPL · **Subject:** any claim an agent makes about the world, and
whether it can be checked. · **Authority:** `HUMAN://ROOT`.

This is the laboratory inside `C:\æ`. It is not a robotics laboratory. A
robotics laboratory's unit is the robot; **ours is the receipt.**

The claim that defines it: a thing that has not been checked back is not a
thing. Everything here exists to make that checkable by anyone, on a laptop,
with no account and no lab.

## Instruments (what we own)

| Layer | Instrument | Returns |
|---|---|---|
| custody → delivery | `væult://` — the 9-link chain (custody, format, gate, authority, contract, dispatch, publish, delivery, adoption) | a sealed, receipted handoff |
| pixel oracle | `tinycuda` | reward 1.0 / 0.0, zero tokens |
| motion oracle | `tinymujoco` | byte-identical trace, or a separation number |
| bus oracle | `tinycan` | event-trace hash |
| seam oracle | `tinycudavideo` | pixels **and** mux — finds the frozen-tail films the pixel gate passes |
| time oracle | `tinycontinuum` | gaps / freezes / reversals |
| ledger | `tinyfilmmemory` | hash-chained corpus + audit (DRIFT when bytes change) |
| plugin oracle | `tinyplugin` | static defect detection |
| governance | `asimov://` C2 | plan, never an act; motion requires a human; never self-grants |
| provenance | SHA-256 receipts, `H(prev ∥ intent ∥ ops ∥ result ∥ state ∥ evidence)` | a citation, not a caption |

## Subjects (what the instruments are pointed at)

Robotics (the Asimov humanoid — governed simulation, hardware-ready), film
(the paper, in 9:16), and any surface that makes a claim.

## Rules

1. **A thing that has not been checked back is not a thing.** The parent's own
   sha + gate is the receipt, never a child's self-report.
2. **Evidence ≠ authority.** A measurement is not a permission.
3. **A refusal is a result.** `{"ok": false, "refused": true}` is a correct
   answer; never route around the gate.
4. **Never move a secret.** Custody is local; surfaces are public truth only.
5. **Fix the scene, never the threshold.** A gate refusal is repaired in the
   artifact, not by lowering the gate.
6. **Every run leaves the lab measurably better.** Each run appends
   **proved / broke / change** to a run log, and the `change` is applied in the
   same session. A run that finds nothing to change was not looking.
7. **Gate the seams, not the components.** Defects live where two things meet
   (picture/voice, sim/policy, policy/render, render/receipt) — each seam gets
   its own assertion.

## Scorecard (honest, as of 2026-11-21)

- **Punches above its weight:** auditability. Every artifact carries a
  reproducible receipt; the whole estate can be re-derived and checked.
- **At its weight:** deterministic simulation. Renders, traces and receipts
  are byte-reproducible; the claims are labelled `sim`.
- **Below its weight:** hardware. Zero physical acts. The lab's honesty depends
  on never blurring this line.

## What it is not

Not a robotics lab in the institutional sense. Not a model lab (the policy is
consumed, not trained here). Not a cloud. It is the **governance-and-provenance
layer** that the other labs lack — and the reason a one-person company can make
a claim that survives scrutiny.
