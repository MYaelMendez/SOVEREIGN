# tinyMuJoCo — headless deterministic physics oracle

## What it measures

tinyMuJoCo grades **motion**. MuJoCo physics is bit-reproducible, so a trajectory
hash is a zero-token, zero-model-call grade: reward is 1.0 or 0.0, with no judge
and no partial credit. tinyCUDA grades pixels; tinyMuJoCo grades motion.

It is a **simulation instrument**, not a robot controller. It plans and verifies
trajectories; a trace is a plan, never an act.

Shape: `tinymujoco.py` (verbs + `doctor()` + refusals), `tests/test_tinymujoco.py`,
`provenance.py` (seal / seal-walk / verify / qr / memory), and
`film/make_film.py` + `film/RUNBOOK.md` (composed explainer film).

## Measured on this host

Re-run with `C:/gpu/Scripts/python.exe` (MuJoCo is not in the default interpreter):

```
doctor          → ok:true · mujoco 4.0.1 · numpy 2.2.6 · headless:true
                  · opengl_required:false · display_required:false
                  · smoke: 10 steps, qpos[2]=-0.002158 · timestep 0.002
pytest          → 21 passed in 1.82s
sim ledger      → 3 sealed records, chain VALID, head 16bd1805ff3f830c…
                  · grants:false · executed:false · hardware:false
hero trace      → receipt 805b855be6c457ba… · travel 1.0838 m
                  · 400 policy ticks / 1600 physics steps · 10.71× realtime
film            → tinymujoco-contract-916.mp4 · 11,069,417 B
                  · sha256 9bad37b1b7863f97de298bdb9aef574d467c24fe75b33d864cc196ed31519d4a
                  · 1305 frames · 720×1280 · 24 fps · 54.375 s
gate            → luminance 34.7 · contrast 38.49 · motion 3.383 · black 0%
                  · mux delta 0.000 s · SupervisorVideo PASS · board_approved:false
```

The film sha256 matches the citation in `film/RUNBOOK.md` and the filmemory
record byte-for-byte. The QR (`traces/qr-805b855be6c457ba.png`) is the same
artifact shown in scene S4; encode → decode → pyzbar scan-back is recorded in
the RUNBOOK.

## Refusals pinned by tests

Seed-inert on unactuated models; qpos0 shape refusal; malformed/missing model
refusal; zero-token grade; prefix-is-not-a-reproduction; single-element edit
detection; ledger `grants:false/executed:false/hardware:false`.

## Limits

- **Simulation only.** No physical robot is actuated. Motion verbs require a
  bound human approval or an armed deadman; a rollout never grants authority.
- **Determinism is scoped to the TRACE**, not the composed film — the
  least-deterministic-stage law applies (voice synthesis is not deterministic).
- **A rollout's `success` and an independent `verify()` disagree by design.**
  `success` is per-segment (upright ∧ every commanded segment obeyed);
  `verify()` is whole-trace (not fallen ∧ end-state obeyed). A `success:false`
  beside a `verify` ok is a finding about scope, not a bug — cite both.
- **A commanded velocity is BODY-FRAME.** After a `wz` turn, a `vy` strafe
  follows the new heading. Judge each segment, not just end displacement.
- **Not published.** `board_approved:false` in `film/deliverables/meta.json`;
  the film awaits the human gate and `kanban_push.py`.
- This README was added from a re-run audit on 2026-11-22; the instrument and
  its sealed artifacts are earlier work (Nov 19–20). The README documents the
  measured state; it does not claim authorship of the build.

## Run

```bash
PY="env -u PYTHONPATH -u PYTHONHOME C:/gpu/Scripts/python.exe"
$PY tinymujoco.py doctor
$PY -m pytest tests/test_tinymujoco.py -q
$PY provenance.py selftest
```
