# VSCODER://BRIDGE

Hermes Desktop IDE driver — typed VSCODER tools over authenticated IPC/RPC with full IDE control, state observation, and authority separation.

## Architecture

The VSCODER://BRIDGE exposes six TypeScript modules over localhost WebSocket + JSON-RPC 2.0:

| Module | Responsibility |
|--------|---------------|
| `ipc.ts` | JSON-RPC 2.0 over TCP, localhost-only, session auth (TTL 30min), 64KB payload cap |
| `state.ts` | IDEStateObserver — VSCODER_IDE_STATE_V1 versioned snapshots with compact deltas |
| `resolver.ts` | CommandResolver — classifies effects as LOCAL / DURABLE / EXTERNAL; fail-closed |
| `plan.ts` | PlanValidator — workspace_hash SHA-256, 409 PLAN_STATE_CONFLICT on state drift |
| `capabilities.ts` | 11 typed namespaces (debug, diagnostics, editor, ide, refactor, scm, task, test, terminal, workspace, …) |
| `events.ts` | EventStream — delta chain, secret exclusion via sanitize() |

## Authority Model

```
LOCAL     — no grant needed (read-only, in-memory, ephemeral)
DURABLE   — policy/confirmation required (persistent state changes)
EXTERNAL  — passkey + transaction-bound grant required (network, APIs)
```

`ui.executeCommand(anything)` never resolves to LOCAL. Unknown commands are denied (fail closed).

## Commands

| Command | Title |
|---------|-------|
| `vscoderBridge.open` | VSCODER://BRIDGE Open |
| `vscoderBridge.observe` | VSCODER://BRIDGE Observe IDE State |
| `vscoderBridge.plan` | VSCODER://BRIDGE Plan |
| `vscoderBridge.refactor` | VSCODER://BRIDGE Refactor |
| `vscoderBridge.build` | VSCODER://BRIDGE Build |
| `vscoderBridge.test` | VSCODER://BRIDGE Test |
| `vscoderBridge.debug` | VSCODER://BRIDGE Debug |
| `vscoderBridge.benchmark` | VSCODER://BRIDGE Benchmark |
| `vscoderBridge.gitDiff` | VSCODER://BRIDGE Git Diff |
| `vscoderBridge.receipt` | VSCODER://BRIDGE Receipt |

## Building

```bash
npm install
npm run compile
npm run package
```

## License

MIT
