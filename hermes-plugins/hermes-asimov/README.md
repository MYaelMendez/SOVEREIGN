# Hermes-Agent://asimov

> Governed verbs. Menlo's own wire names. Receipted authority.

**`hermes-asimov` — first-class Hermes Agent package · wraps the official Menlo SDK · Apache-2.0 · Hermes ≥0.22.2**

`hermes-asimov` packages `asimov://` — the OpenSourceWare command-and-control
protocol for the Asimov 1 humanoid by Menlo Research — as a first-class Hermes
plugin. It wraps the official [menlo-sdk](https://github.com/menloresearch/menlo-sdk)
(0.1.0, Apache-2.0). It invents no wire synonyms: every motion name is Menlo's
own verb. On top of the SDK it adds the two things the SDK deliberately leaves
to user code — an authority gate (æ Policy) and a hash-chained receipt — and
specifies one transport the SDK does not ship: `sim`, so the same C2 path can
run on a laptop with no robot.

```text
HUMAN://ROOT → æ POLICY → asimov:// → menlo.asimov.Robot → RECEIPT
```

> **Thank you to [Menlo Research](https://github.com/menloresearch)** for
> open-sourcing the Menlo SDK and the Asimov 1 CAD, and to
> [Nous Research](https://nousresearch.com) for Hermes Agent. We built the
> governance layer; you built the source. #opensourceware #internetofagents

> **Status, plainly.** No physical robot has been driven by this plugin. Every
> result it has produced is a plan or a refusal. The `sim` transport (MuJoCo)
> is an OpenSourceWare addition that is being built separately — it is
> specified, not implemented. Never report a simulated act as a physical one.

- **Version:** 0.2.0 (`cast.json` carries `"version": "0.2.0"`; the `version`
  field in `plugin.yaml` still reads `0.1.0` and was left unchanged by this
  packaging pass — see [CHANGELOG.md](CHANGELOG.md))
- **Plugin destination:** `$HERMES_HOME/plugins/hermes-asimov`
- **Protocol engine:** `scripts/asimov_protocol.py` (dispatches `asimov://` addresses)
- **Verb engine dependency:** the `hermes-ae` plugin's `scripts/ae_verbs.py` — wrapped, never reimplemented
- **Receipt ledger:** `$HERMES_HOME/asimov-protocol.jsonl` (override with `HERMES_ASIMOV_LEDGER`)

## What ships

| Path | Purpose |
|---|---|
| `plugin.yaml` | Manifest: six tools, version, and Hermes requirement |
| `__init__.py` | Registers the six `asimov_*` tools and the system-prompt section |
| `cast.json` | White-label cast, colours, voice derivations, brand, and authority string (schema `hermes-asimov/cast/1`) |
| `scripts/asimov_protocol.py` | The `asimov://` protocol engine: policy-gated plans, executions, receipts, fail-closed routing |
| `scripts/cast_config.py` | White-label loader: resolves `cast.json`, falls back to a neutral default, refuses malformed configs |
| `scripts/sim_transport.py` | SimTransport (MuJoCo) — work in progress, being built separately; not operational |
| `dashboard/manifest.json` + `dashboard/plugin_api.py` | Read-only dashboard backend: status, cast, receipt ledger, policy-evaluated plans. Grants no authority |
| `tests/test_plugin.py` | Safety regression tests: motion gating, confirm gate, no self-grant, refusals as results |
| `install.sh` | Copies the plugin into `$HERMES_HOME/plugins/hermes-asimov`; does not enable it |
| `README.md` | This document |
| `LICENSE` | Apache License, Version 2.0 |
| `NOTICE.md` | Upstream attribution: Menlo Research and Nous Research |
| `CHANGELOG.md` | Keep a Changelog history |

The installer also copies `docs/` and the desktop pane assets
(`dashboard/dist/`) when they are present alongside it; each item is
existence-guarded, so a partial checkout still installs cleanly. The desktop
pane and docs are still being built.

## Requirements

- Hermes Agent ≥0.22.2 with plugin loading.
- The `hermes-ae` plugin at `$HERMES_HOME/plugins/hermes-ae` (override with
  `HERMES_AE_HOME`). It owns the verb surface (`scripts/ae_verbs.py`) and the
  æ Policy rules. Without it, every `asimov://` call fails closed with a
  refusal — that is the designed behavior, not a bug to route around.
- Python 3.11+ for the child interpreter (select with `HERMES_AE_PYTHON`).
- [menlo-sdk](https://github.com/menloresearch/menlo-sdk) 0.1.0
  (`pip install menlo-sdk`) — the official client, required for live SDK
  calls. Status and planning report honestly when it is not installed.
- MuJoCo — the intended engine for the `sim` transport. The transport itself
  is being built separately and is not implemented yet.

No credentials, tokens, or network access are needed to plan. Execution is
dry-run unless `HERMES_AE_SDK_LIVE=1` **and** `confirm=true`, and motion still
requires a bound human approval or an armed deadman.

## Install

```sh
sh install.sh
```

The script copies the plugin payload into `$HERMES_HOME/plugins/hermes-asimov`
(`HERMES_HOME` defaults to `$HOME/.hermes`). It never prompts for secrets and
writes nothing outside the Hermes home.

**The installer does not enable the plugin.** Enable it yourself:

```sh
hermes plugins enable hermes-asimov
```

or add `hermes-asimov` to the `plugins.enabled` list via
`hermes config set plugins.enabled`. Enabling takes effect in the **next**
Hermes session — restart Hermes afterwards.

## Plugin tools

The plugin registers six top-level tools:

| Tool | Action |
|---|---|
| `asimov_status` | Protocol status: Menlo SDK version, robot presence, transports, verb count |
| `asimov_verbs` | The canonical verb set, mapped to official Menlo SDK calls, with class and gate |
| `asimov_plan` | Policy-evaluated plan; returns the exact SDK call. **Never connects.** The default safe path |
| `asimov_exec` | Execute a verb. Requires `confirm=true`; stays dry-run unless `HERMES_AE_SDK_LIVE=1` |
| `asimov_sim` | Plan against the MuJoCo simulation transport. Requires no robot. Transport specified, not yet implemented |
| `asimov_grant` | Report the approval shape a verb requires. **Grants nothing** — only `HUMAN://ROOT` signs |

Example calls:

```text
asimov_status({})
asimov_verbs({})
asimov_plan({"verb": "stand"})
asimov_grant({"verb": "trajectory"})
asimov_sim({"verb": "balance"})
asimov_exec({"verb": "state", "confirm": true})
```

A refusal is a correct answer:

```json
{"ok": false, "refused": true, "reason": "execution requires confirm=true"}
```

Report it; do not retry around the gate.

## The 14 verbs

Motion names are Menlo's own; this plugin invents no wire synonyms.

| Verb | Class | Gate |
|---|---|---|
| `status` | read | allowed, with a receipt |
| `state` | read | allowed, with a receipt |
| `get_state` | read | allowed, with a receipt |
| `check` | read | allowed, with a receipt |
| `stand` | motion | human approval or armed deadman (ACT-001) |
| `damp` | motion | human approval or armed deadman (ACT-001) |
| `balance` | motion | human approval or armed deadman (ACT-001) |
| `set_velocity` | motion | human approval or armed deadman (ACT-001) |
| `trajectory` | motion | human approval or armed deadman (ACT-001) |
| `set_joints` | motion | human approval or armed deadman (ACT-001) |
| `photo` | media | allowed, with a receipt |
| `capture_clip` | media | allowed, with a receipt |
| `record_audio` | media | allowed, with a receipt |
| `play_pcm` | media | allowed, with a receipt |

Motion verbs return `require_approval` until a bound human approval or an
armed deadman exists. An agent cannot supply either, and `asimov_grant`
returns `grants: false` — it reports the required shape, it never authorizes.

## Transports

| Transport | Official | Requires | Media |
|---|---|---|---|
| `udp` | yes (Menlo SDK) | robot on a trusted LAN | no |
| `hybrid` | yes (Menlo SDK) | robot + LiveKit | yes |
| `livekit` | yes (Menlo SDK) | robot + room | yes |
| `sim` | no — OpenSourceWare addition | a laptop (MuJoCo) | yes |

The three official transports need a robot. `sim` is ours: same verbs, same
gates, same receipts, no hardware. **SimTransport is being built separately;
it does not work yet.** Today `asimov_sim` returns a plan marked
`transport not yet implemented — plan only`.

## Rules that bind every agent

1. **An address is not a permission.** Resolving a verb produces a plan, never
   an act. `asimov_plan` is the default safe path; it never connects.
2. **Motion requires a human.** The six motion verbs stay gated until a bound
   human approval or an armed deadman exists.
3. **Never self-grant.** Do not fabricate an approval object. Only the human
   signs.
4. **A refusal is a result.** `{"ok": false, "refused": true, ...}` is a
   correct answer, not an error to retry around.
5. **`sim` is not hardware.** Never report a simulated act as a physical one.
6. **Execution is EXTERNAL.** `asimov_exec` needs `confirm=true` and stays
   dry-run unless `HERMES_AE_SDK_LIVE=1`. Ask the operator first.

Unknown routes fail closed: an unrecognized `asimov://` address is a refusal,
never a silent fallthrough.

## Receipts

Every plan and execution appends a receipt to the JSONL ledger at
`$HERMES_HOME/asimov-protocol.jsonl` (override with `HERMES_ASIMOV_LEDGER`).
Actions are `ASIMOV://PLAN` and `ASIMOV://EXEC`. Each entry records `ts`,
`action`, `authority` (`HUMAN://ROOT`), `detail`, `prev`, and `hash`. The chain
begins with `prev` equal to 64 zeroes; each `hash` is the SHA-256 of the
canonical JSON of the entry (including `prev`), so every link binds the one
before it. This is a local tamper-evident chain: it evidences what was
requested and decided, not cryptographic authenticity.

## White-label: cast.json

`cast.json` (schema `hermes-asimov/cast/1`) carries the entire presentation and
authority identity. **A different operator edits `cast.json`, not the code.**
`scripts/cast_config.py` loads it: explicit path → `$HERMES_ASIMOV_CAST` →
`<plugin_dir>/cast.json` → built-in neutral default. A missing file falls back
(and says so); a malformed config is a structured refusal, never silently
repaired.

- **Cast** — five members with roles, head colours (`head_rgb`), filename
  prefixes, and voice derivations from the two base timbres:

| id | Role | Voice |
|---|---|---|
| `nous` | root voice | base `F2` |
| `hermes` | build voice | base `M2` |
| `waetz` | human digital twin · test pilot (the center) | derived from `M2` |
| `menlo` | upstream source | derived from `M2` |
| `asimov` | robot body | derived from `F2` |

- **Brand** — gold `#D4AF37` on void `#050505`, prompt `>_æ://`, title
  `æ:// MIXTURE OF ROBOTS`, tagline `MENLO CAD · NATIVE MUJOCO · LOCAL`,
  monospace font stack.
- **Authority** — the `HUMAN://ROOT` string, and the policy block
  (`fail_closed: true`, `motion_requires: human_approval_or_armed_deadman`,
  rules source `ae-policy.json`).
- **States** — eight conversation states (`IDLE`, `LISTENING`, `THINKING`,
  `SPEAKING`, `AWAITING_APPROVAL`, `APPROVED`, `REFUSED`, `ERROR`), each with
  an RGB colour, head pitch, and yaw.
- **Stage** — `separation_m` spacing and an 18-language list.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `HERMES_HOME` | `$HOME/.hermes` | Hermes home; ledger and plugin paths derive from it |
| `HERMES_AE_HOME` | `$HERMES_HOME/plugins/hermes-ae` | Root of the verb-engine plugin |
| `HERMES_AE_PYTHON` | current interpreter | Python used for the protocol child process |
| `HERMES_AE_SDK_LIVE` | unset (dry-run) | Set to `1` to allow live SDK execution (still gated) |
| `HERMES_ASIMOV_LEDGER` | `$HERMES_HOME/asimov-protocol.jsonl` | Receipt ledger path |
| `HERMES_ASIMOV_CAST` | `<plugin_dir>/cast.json` | White-label cast config path |
| `MENLO_ROBOT` / `MENLO_UDP_HOST` | unset | Robot presence reported by `asimov_status` |

## Safety boundary

The Menlo SDK is a client of Asimov Edge and its safety layer, **never a
bypass**. Nothing in the SDK is an emergency stop. This plugin adds
governance — policy gates, approvals, receipts — not physical safety. Physical
safety remains with the robot's own safety layer and the human operator.

## Limits

- **No physical robot has been driven.** Every result so far is a plan or a
  refusal.
- **`sim` is specified, not implemented.** SimTransport is being built
  separately; `asimov_sim` is plan-only today.
- Motion verbs cannot be executed by an agent alone; a human approval or an
  armed deadman is required.
- The verb engine lives in `hermes-ae`; without it, all calls refuse.
- Receipts are a local tamper-evident chain, not a cryptographic signature.

## License and upstream

Plugin packaging and documentation are released under the terms in
[LICENSE](LICENSE) (Apache-2.0). Upstream components remain under their own
licenses — see [NOTICE.md](NOTICE.md):

- [menloresearch/menlo-sdk](https://github.com/menloresearch/menlo-sdk) — Apache-2.0 (official SDK, wrapped unchanged).
- [menloresearch/asimov-1](https://github.com/menloresearch/asimov-1) — Apache-2.0 (CAD; meshes hash-bound in `asimov-avatar.usda`).
- [Hermes Agent](https://hermes-agent.nousresearch.com) — Nous Research (plugin runtime).

`HUMAN://ROOT` is an attribution marker for the receipt ledger, not a software
license.

## Thanks

Thank you again to [Menlo Research](https://github.com/menloresearch) for the
open SDK and CAD that made this development possible, and to
[Nous Research](https://nousresearch.com) for Hermes Agent.

#opensourceware #internetofagents
