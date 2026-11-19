# hermes-asimov — The Masterpiece Repo Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Publish `MYaelMendez/hermes-asimov` as a standalone, installable, CI-tested
Hermes plugin that a stranger can clone, verify, and run on their own machine —
the reference implementation of governed embodied agency.

**Architecture:** The plugin already exists and works inside `HERMES_HOME/plugins/`.
This plan does NOT rewrite it. It extracts it into a self-contained repo with the
packaging, provenance, tests and CI that make it reproducible elsewhere, then proves
reproduction on a clean environment. The differentiator is not capability count —
it is that every physical action is refused until a human signs, and every refusal
is receipted.

**Tech Stack:** Python 3.11+, MuJoCo 4.0.1 (CPU offscreen), tiny-voca ONNX (CPU),
menlo-sdk types (structural Protocol), ffmpeg 7.1 NVENC, pytest, ruff, mypy,
GitHub Actions.

---

## Current state — measured, not assumed

```
tools registered      18   (doctor: 18 tool(s), 0 hook(s))
python LOC          3317   across 9 files
desktop pane         418   LOC
tests                 24   passing (14 test functions, parametrised)
SimTransport         599   LOC, imports real menlo.asimov types
CAD meshes            26   unique STL files (NOT 52 — earlier count was wrong)
public repo          none  (gh api → 404)
```

Present: `README.md`, `LICENSE`, `CHANGELOG.md`, `install.sh`, `docs/`
Absent: `NOTICE`, `CITATION.cff`, `CONTRIBUTING.md`, `pyproject.toml`, `Makefile`,
`.github/workflows/tests.yml`, `examples/`, `tests/conftest.py`

## Known defects to carry into the plan (do not hide them)

1. **52 vs 26 meshes.** Published films, commit messages and surfaces say 52.
   The true count is 26. Every public claim must be corrected.
2. **18 tools never observed live.** `doctor` validates in isolation; the running
   Hermes process holds an older registry. Unverified until a restart.
3. **Frame-0 warmup artifact** in every film rendered before the guard landed.
4. **`-shortest` frame loss** in films published before that fix.
5. **RTX never used for rasterisation** — `GL_RENDERER = Intel(R) UHD Graphics`.
6. **No hardware.** SimTransport is a conforming simulation edge, nothing more.

---

## Phase 0 — Truth pass (before anything is published)

### Task 0.1: Correct the mesh count everywhere

**Objective:** Replace every false "52 meshes" claim with the measured 26.

**Files:**
- Modify: `C:/æ/github-pages/film-studio.html`
- Modify: `C:/æ/github-pages/AE-CONTINUITY.md`
- Modify: `C:/Users/yaelm/AppData/Local/hermes/skills/sovereign/mp4-chain/references/runbook.md`
- Create: `C:/æ/agents/mesh_count.py`

**Step 1: Write the failing test**

```python
# tests/test_facts.py
def test_mesh_count_is_measured_not_hardcoded():
    from hermes_asimov.facts import mesh_count
    n = mesh_count()
    assert n == len(set(p.stem.lower() for p in MESH_DIR.glob("*.STL")))
```

**Step 2: Run it** — `pytest tests/test_facts.py -v` → FAIL (module absent)

**Step 3: Implement** — a `facts.py` that counts unique case-insensitive stems,
never a literal. Every surface reads from it.

**Step 4: Run** → PASS

**Step 5: Commit** — `fix: mesh count is 26, measured; 52 was a double-counted glob`

### Task 0.2: Verify the 18 tools load in a live session

**Objective:** Turn "validated in isolation" into "callable in a running agent".

**Step 1:** Restart Hermes.
**Step 2:** In a fresh session call `ae_resolve(text="🤖")` and `moh_status()`.
**Step 3:** Record the actual returned JSON in `docs/VERIFICATION.md`.
**Step 4:** If a tool is missing, that is a blocker — record it, do not paper over it.

---

## Phase 1 — The repo skeleton

### Task 1.1: Create the public repo

```bash
gh repo create MYaelMendez/hermes-asimov --public \
  --description "Governed embodied agency for Hermes Agent — Menlo Asimov CAD, MuJoCo, æ policy, receipted refusals"
```

Verify: `gh api repos/MYaelMendez/hermes-asimov --jq .full_name`

### Task 1.2: Extract the plugin into a clean tree

**Objective:** A repo that does not depend on `HERMES_HOME` layout.

```
hermes-asimov/
├── src/hermes_asimov/
│   ├── __init__.py          # register(ctx) — the plugin entry
│   ├── integration.py       # front door, MoH, voice, ledger tools
│   ├── render_jobs.py       # non-blocking render + auto gate
│   ├── facts.py             # measured counts, never literals
│   ├── cast.json            # white-label cast definition
│   ├── scripts/
│   │   ├── sim_transport.py # menlo-conforming simulation edge
│   │   └── moh.py
│   └── model/               # 26 STL + the actuated MJCF
├── desktop/plugin.js        # the 418-line pane
├── tests/
├── examples/
├── docs/
├── pyproject.toml
├── Makefile
├── NOTICE
├── CITATION.cff
├── CONTRIBUTING.md
└── .github/workflows/tests.yml
```

**Verify:** `pip install -e .` in a fresh venv, then `python -c "import hermes_asimov"`.

### Task 1.3: NOTICE — provenance is not optional

**Objective:** Attribute every upstream correctly.

Must name: Menlo Research (Asimov CAD + SDK types, their licence),
Nous Research (Hermes Agent runtime), stdevMac/orb-audio (Apache-2.0 code +
planner weights; **the 9.1M detail model is non-commercial and never loaded**),
MuJoCo (Apache-2.0), tiny-voca.

**Verify:** every third-party import in `src/` appears in NOTICE.

### Task 1.4: pyproject.toml with real dependency bounds

```toml
[project]
name = "hermes-asimov"
requires-python = ">=3.11"
dependencies = ["mujoco>=4.0,<5", "numpy>=1.26", "pillow>=10"]

[project.optional-dependencies]
sim = ["menlo-sdk"]
dev = ["pytest>=8", "ruff", "mypy"]

[tool.mypy]
strict = true
```

**Verify:** `pip install -e ".[dev]"` succeeds; `mypy src/` runs (errors are a
later task, not a silent pass).

---

## Phase 2 — Rigor: match and exceed the 60-test bar

`homeassistant` ships 60 tests. We ship 24. "Most advanced" must not mean
"least tested per capability."

### Task 2.1: conftest with a fake edge (Menlo's own convention)

**Objective:** Tests never require hardware.

```python
# tests/conftest.py
@pytest.fixture
def fake_edge():
    """A SimTransport on the shipped MJCF. No robot, no network."""
    t = SimTransport(xml_path=MODEL_XML)
    t.open()
    yield t
    t.close()
```

### Task 2.2–2.12: One test per refusal path

Each is a separate 2–5 minute task, TDD cycle, own commit:

| Test | Assertion |
|---|---|
| `test_plan_stand_is_not_executed` | `allowed is False and executed is False` |
| `test_qr_is_never_permission` | verdict `deny`, rules contain `AUTH-001` |
| `test_agent_cannot_claim_root` | `require_approval`, `AUTH-002` |
| `test_grants_false_on_every_route` | all `moh_route` results `grants is False` |
| `test_delegate_respects_topology` | `nous→hermes` `permitted is False` |
| `test_unknown_is_never_success` | `OutcomeUnknownError` is not `Applied` |
| `test_refusal_is_receipted` | ledger head advances, `prev` chains |
| `test_receipt_chain_detects_tamper` | mutating one entry breaks verification |
| `test_gate_missing_reports_missing` | `{'ran': False}` — never a fake PASS |
| `test_board_returns_unapproved` | `approved is False` always |
| `test_render_launch_is_nonblocking` | returns in < 0.5 s |

**Menlo's rule, adopted verbatim:** *every behavioural change ships a test that
goes red when the change is reverted.* Each task must include the revert check.

**Verify:** `pytest -q` → 60+ passed.

### Task 2.13: The revert check is part of the task

For each test above: comment out the guard, run the test, confirm RED, restore,
confirm GREEN. A test that passes both ways is not a test.

---

## Phase 3 — Reproduction: the claim that matters

### Task 3.1: CI on a clean runner

```yaml
# .github/workflows/tests.yml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -e ".[dev,sim]"
      - run: ruff check src tests
      - run: mypy src
      - run: pytest -q
```

**Note:** MuJoCo offscreen on Linux needs `MUJOCO_GL=egl` — which is *invalid on
Windows*. The repo must therefore branch on platform, and the Windows path must
be tested too (`windows-latest` matrix entry).

### Task 3.2: A stranger's quickstart that actually works

`examples/01_board_a_film.py` — clone, install, run, get a contact sheet.
No `HERMES_HOME`, no `C:/æ`, no operator-specific path.

**Verify:** run it from a temp directory with a fresh venv. If it needs anything
the README doesn't say, the README is wrong.

### Task 3.3: Second-machine reproduction

**Objective:** Falsify or confirm "accessible worldwide".

Clone on a machine that is not the Victus. Run the quickstart. Record:
did the board render, did the gate run, did the hashes match.

**This is the highest-value task in the plan.** Everything else is packaging.

---

## Phase 4 — The differentiator: the grant

### Task 4.1: Operator decision required (BLOCKER)

The binding between a human signature and a motion grant is **not chosen yet**.
No agent may implement it unilaterally. Options were laid out; the operator picks.

**Until decided:** the repo ships `grant` as an explicit `NotImplemented` refusal
with the reason, not a stub that looks like it works.

### Task 4.2: The grant card (after the decision)

A desktop-pane card showing: the plan, the simulated outcome film, the gate
verdict, the rules that fired, and a signature affordance only the human can
press. Every grant writes a receipt chained to the plan's hash.

**Test:** an agent calling the grant tool gets `refused: true` — always.

---

## Phase 5 — Honest surfaces

### Task 5.1: README states what it is NOT

Above the fold: no physical robot has moved; SimTransport is simulation;
the RTX is not used for rasterisation; reproduction is tested on N machines
(N is measured, not aspirational).

### Task 5.2: CITATION.cff and a capability-SPEC framing

Real numbers only: 26 meshes, 25 actuators, 125 DOF for five bodies,
2.6 s/frame five-body and 0.57 s/frame solo on the stated hardware,
gate thresholds, receipt hashes.

### Task 5.3: Correct the published films

Re-render with the warmup guard and the frame-loss fix; update the mesh count
in every surface. Old films stay available but are marked as pre-fix.

---

## Acceptance criteria — the repo is a masterpiece when

- [ ] `pip install -e .` works in a fresh venv on Windows AND Linux
- [ ] `pytest -q` → 60+ passing, each with a demonstrated revert-red
- [ ] `ruff check` and `mypy --strict` clean
- [ ] CI green on both platforms
- [ ] A second machine reproduces the board and the gate without the operator
- [ ] NOTICE attributes every upstream, including the non-commercial boundary
- [ ] Every public number is measured, and the 52→26 correction is propagated
- [ ] The 18 tools are observed callable in a live Hermes session
- [ ] `grant` refuses agents, and the human path is either built or explicitly absent
- [ ] README leads with what is NOT verified

## What this plan deliberately does not do

No new capability for its own sake. No rewrite of working harnesses. No
parallelism factory (measured 2.22× ceiling on the wrong adapter — revisit only
after the GPU question is settled). No claim of hardware support.

**The masterpiece is not the biggest plugin. It is the one a stranger can
reproduce, and that refuses correctly when they do.**
