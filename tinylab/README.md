# tinyLAB — the studio's recursive self-study

The studio is a learning laboratory only if it **learns about itself**. Every
other `tiny*` instrument measures something else — pixels, motion, time, a
ledger, a policy, a film. tinyLAB measures the laboratory, and feeds its own
verdict back as the next instruction.

```
run → receipt → study (the lab grades itself) → change → next run
```

That is the recursion: **the artefact of a run becomes the input of the next.**

## Surface

| verb | what it does |
|---|---|
| `instruments` | the tiny* family present, with test counts read from the tree |
| `doctor` | the lab's own state — present / tested / **untested** |
| `selftest [name]` | run the instruments' suites; a green suite is a measurement |
| `study` | the lab grades itself → **one receipt** |
| `next` | the last study's `change` → the next brief |
| `ledger` | the lab's hash chain |

## The four rules, one level up

1. `doctor` measures the estate; it never asserts a capability.
2. Every instrument must have a **refusal path**, and the tests must pin it.
3. The ledger records **decisions**; tamper must be detectable.
4. The contract is read **from the artifact** — an instrument is what its tests
   and its refusals say it is, not what its name says.

## What the study does

It inventories the family, runs every suite, and writes one receipt carrying:
`present`, `tested`, `untested`, `selftest_ok`, `passed/total`, the **previous**
study's change, and this study's `change` — the instruction the laboratory gives
itself next. `next` reads it back.

## Tests

6 tests pin the inventory, the untested report, the receipt→brief recursion
(both directions), the `prev_change` chain, and ledger tamper. The slow
full-suite run is the `study` verb itself, not a test.

## Limits

- The lab grades **its own instruments**, not the truth. A green suite means the
  refusals are pinned, not that the world agrees.
- `selftest` uses `sys.executable`; a suite needing a different interpreter
  (CuPy) reports as failing here even though it passes in its own runtime.
- The loop closes on **process**, not on physics: the `change` is a brief for
  the next run, not a retrained gait.
