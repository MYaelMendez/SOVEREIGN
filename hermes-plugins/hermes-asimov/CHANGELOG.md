# Changelog

All notable changes to `hermes-asimov` are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

SimTransport (MuJoCo) is being built separately. Until it lands, `asimov_sim`
is plan-only and no simulated actuation is claimed. No physical robot has been
driven; every result so far is a plan or a refusal.

## [0.2.0] - 2026-11-18

### Added

- `cast.json` white-label file (schema `hermes-asimov/cast/1`): the cast,
  colours, voice derivations, brand, and authority string. A different
  operator edits `cast.json`, not the code.
- Dashboard backend for the plugin's scoped API.
- Desktop pane.
- Tests.
- Packaging: `README.md`, `install.sh`, `LICENSE` (Apache-2.0), `NOTICE.md`
  (Menlo Research and Nous Research attribution), and this `CHANGELOG.md`.

### Notes

- The `version` field in `plugin.yaml` remains `0.1.0` in this pass; the
  manifest was intentionally left unchanged by packaging. `cast.json` carries
  `"version": "0.2.0"`.
- Transports `udp`, `hybrid`, and `livekit` are official Menlo SDK transports
  and require a robot. `sim` is an OpenSourceWare addition, specified but not
  yet implemented.

## [0.1.0] - 2026-11-18

### Added

- Six registered Hermes tools: `asimov_status`, `asimov_verbs`, `asimov_plan`,
  `asimov_exec`, `asimov_sim`, `asimov_grant`.
- System-prompt section (`asimov-protocol`) teaching the binding rules: an
  address is not a permission; motion requires a human; never self-grant; a
  refusal is a result; `sim` is not hardware; execution is EXTERNAL.
- `scripts/asimov_protocol.py`: the `asimov://` dispatcher over the official
  Menlo SDK verb surface (via the `hermes-ae` verb engine), with hash-chained
  `ASIMOV://PLAN` / `ASIMOV://EXEC` receipts and fail-closed unknown routes.
- 14 verbs in three classes: read (`status`, `state`, `get_state`, `check`),
  motion (`stand`, `damp`, `balance`, `set_velocity`, `trajectory`,
  `set_joints`), and media (`photo`, `capture_clip`, `record_audio`,
  `play_pcm`). Motion requires human approval or an armed deadman; read and
  media verbs are allowed with a receipt.
