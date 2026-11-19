# Third-Party Notices

> **Thank you to [Menlo Research](https://github.com/menloresearch)** for
> open-sourcing the [Menlo SDK](https://github.com/menloresearch/menlo-sdk)
> and the [Asimov 1 CAD](https://github.com/menloresearch/asimov-1). This
> integration exists because you released the source openly. Thank you also
> to [Nous Research](https://nousresearch.com) for Hermes Agent, the runtime
> this plugin plugs into. We built the governance layer; you built the source.
>
> #opensourceware #internetofagents

`hermes-asimov` is a governance and packaging layer over the official Menlo
SDK. It invents no wire synonyms: every motion name is Menlo's own verb. It
does not vendor the SDK or the CAD; those are upstream works used under their
own licenses.

## Apache-2.0 upstreams

### Menlo Research — menlo-sdk

- **Source:** <https://github.com/menloresearch/menlo-sdk>
- **Version wrapped:** 0.1.0
- **License:** Apache License, Version 2.0.
- The official Python client for Asimov 1. This plugin wraps its verb surface
  (`stand`, `damp`, `balance`, `set_velocity`, `trajectory`, `set_joints`,
  `photo`, `capture_clip`, `record_audio`, `play_pcm`, and the read calls)
  without renaming or reimplementing it.
- The SDK is a client of Asimov Edge and its safety layer, never a bypass.
  Nothing in the SDK is an emergency stop. This plugin adds governance, not
  physical safety.

### Menlo Research — asimov-1 (CAD)

- **Source:** <https://github.com/menloresearch/asimov-1>
- **License:** Apache License, Version 2.0.
- The CAD meshes (STL) come from `menloresearch/asimov-1`. They are referenced
  by the USD avatar `asimov-avatar.usda` (published on the operator's truth
  surface, not bundled in this plugin directory), where each referenced mesh
  is hash-bound with a SHA-256 (`inputs:mesh_sha256`) and the layer records
  `source = "menloresearch/asimov-1"` and `authority = "HUMAN://ROOT"`.

A copy of the Apache License, Version 2.0 text is provided in [LICENSE](LICENSE).

## Hermes Agent — Nous Research

- **Project:** Hermes Agent, by [Nous Research](https://nousresearch.com).
- **Docs:** <https://hermes-agent.nousresearch.com>
- The plugin API (tool registration, system-prompt sections, dashboard and
  desktop surfaces) is a Hermes Agent capability. `hermes-asimov` is a guest
  in that runtime and claims no ownership of it.

## Runtime dependencies (not vendored)

Used at runtime but installed separately, each under its own license:

- **menlo-sdk** — the official Menlo Research client (Apache-2.0), installed
  with `pip install menlo-sdk`.
- **MuJoCo** — the intended engine for the `sim` transport (DeepMind,
  Apache-2.0). SimTransport is being built separately and is not implemented;
  no simulated actuation is claimed.
- **hermes-ae plugin** — same operator; owns the verb engine
  (`scripts/ae_verbs.py`) and the æ Policy rules. Wrapped, never reimplemented.
- **Python standard library** — `json`, `hashlib`, `subprocess`, `pathlib`,
  `datetime`.

## Attribution note

`HUMAN://ROOT` is the receipt ledger's attribution marker for human authority;
it is not a software license. The authority chain
`HUMAN://ROOT → æ POLICY → asimov:// → menlo.asimov.Robot → RECEIPT` describes
who may act and how the act is recorded — it grants no physical capability.
No physical robot has been driven by this plugin; every result so far is a
plan or a refusal.
