# tinyPOLICY — the robotics command and control for mobility.foundation

The command layer above the tiny family. It composes what already exists; it
invents no motion.

```
HUMAN://ROOT → æ POLICY → mobility.foundation → tinyPOLICY → RECEIPT
```

- **Policy + physics + deadman** come from `tinypython` (`Menlo/asimov1-locomotion-0818`,
  sha `47f70691…88a0c`, MuJoCo 4.0.1, CPU only).
- **The verb surface** is the governed one: `asimov://` authority, no invented verbs.
- **The ledger** is a hash chain over *decisions*, not over intent.

## Rules (inherited, never relaxed)

1. An address is not a permission. `plan` never connects.
2. Motion needs a **fresh presence AND a human signature**. Presence removes ONE
   refusal; it is never a signature.
3. Never self-grant. `exec` returns `grants: false`.
4. A refusal is a result: `{"ok": false, "refused": true, ...}`.
5. Simulation is always allowed — a trace is a picture of a plan.
6. Zero tokens, zero model calls. Deterministic, stdlib + tinypython.

## Surface

| verb | class | needs | effect |
|---|---|---|---|
| `status` `verbs` `ledger` `doctor` `presence` | read | — | read only |
| `plan` | plan | — | a plan, never an act |
| `trace` `verify` | simulate | — | run / check the policy walk |
| `arm` `disarm` `gate` | control | human | presence + the gate |
| `stand` `walk` `set_velocity` | motion | presence + signature | **refused** |

## Use

```bash
tinypolicy.py doctor            # policy, physics, deadman, ledger
tinypolicy.py plan walk         # a plan — connects nothing
tinypolicy.py gate move         # the deadman gate
tinypolicy.py exec stand        # refused: ACT-001 AUTH-002 DEAD-001
tinypolicy.py trace out.json    # the policy walk (simulation)
tinypolicy.py verify out.json   # did it walk, or fall?
```

## Tests

11 tests pin the refusals and the ledger: the verb surface, plan-never-grants,
simulation allowed but never executed, motion refused, gate allow/refuse, the
hash chain, tamper detection, and an honest status.

## Status

`mobility.foundation/c2/1` · schema `mobility.foundation/c2/1` · **11 tests** ·
no hardware commanded — this is a simulation domain whose refusals are the point.
