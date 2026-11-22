# tinyONNX — the policy oracle

Five Menlo Asimov policies exist upstream. They were unpulled and unmeasured.
tinyONNX is the instrument that makes the set **measurable**: it reads the ONNX
contract from the file, refuses a policy that does not match the viewer's
78-in / 23-out contract, rolls a policy out through the pinned physics, grades
the trace, and compares two policies on the same command.

```
policy.onnx → inspect → contract → rollout → grade → receipt
```

It does not reimplement physics — `tinypython` owns the rollout.

## The measured set

| policy | obs | actions | verdict |
|---|---|---|---|
| `0818` | 78 | 23 | **runs** (viewer contract) |
| `26-09-24` | 78 | 23 | **runs** (viewer contract) |
| `26-10-05-upper-body` | 78 | 12 | refused — partial body |
| `26-10-17-upper-body-blind` | 45 | 12 | refused — partial body + narrower obs |
| `26-10-26-lower-body-27dof` | 45 | 12 | refused — partial body + narrower obs |

Three of the four "variants" are **12-action partial-body policies** with a
different observation width. Dropping them into the 23-joint harness would be a
guess about the policy — tinyONNX refuses them and names the actual in/out.

## Use

```bash
tinyonnx.py doctor                 # runtime + the policies present + their contracts
tinyonnx.py inspect <policy.onnx>  # the I/O contract, read from the file
tinyonnx.py contract <policy.onnx> # 78/23? refused if not
tinyonnx.py run <dir> --vx 0.4     # roll out → trace + receipt
tinyonnx.py grade <trace.json>     # recompute the verdict from the trace
tinyonnx.py compare <a> <b>        # two policies, one command
tinyonnx.py ledger                 # the run hash chain
```

Policies live in `C:/æ/policies/<name>/policy/policy.onnx` (override with
`TINYONNX_POLICIES`); runs are recorded in `tinyonnx.jsonl` (`TINYONNX_LEDGER`).

## Tests

10 tests pin the contract check on the real files, the refusal of a
partial-body policy, the baseline rollout + grade, the ledger chain and tamper,
and the two-policy comparison.

## Rules

1. The contract is read from the ONNX, never assumed.
2. A policy that does not match is **refused**, not coerced.
3. Grades are recomputed from the trace, never read from its success flag.
4. Every run is a hash in the ledger; the ledger is a chain.
5. Simulation only — a trace is a picture of a plan.
