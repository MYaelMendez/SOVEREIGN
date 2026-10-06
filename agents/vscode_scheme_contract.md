# `vscode://` Scheme Contract Index

**Scope:** Full specification of the `vscode://` control-plane scheme and the `VSCODER://BRIDGE` — the typed IPC/JSON-RPC substrate that turns VS Code into a Hermes operator surface / first-class agentic engineering primitive.

**Last verified:** Live source files at `C:\æ\vscoder\` and `C:\æ\vscoder-bridge/` (October 2026).

---

## 1. URI Scheme Grammar & Canonical Routes

```
vscode://            → VS Code control plane (entry: open agent panel, dispatch)
vscode://file/<path> → Open file/folder in VS Code editor
vscode://mesh        → Sovereign host + GPU + telemetry liveness (mesh surface)
vscode://gpu         → RTX 3050 compute surface (/matmul, /probe, /telemetry)
vscode://secrets     → Local-only Hermes secret storage surface (vault interop)
vscode://cc          → Command & control surface for the human operator
vscode://home        → homeOS surface (agentic OS hub webview)
```

**Operator grammar** (from `hermes-operator-grammar`):

| Scheme | Meaning |
|--------|---------|
| `c://` | Command prompt operator surface |
| `c://cc <target>` | Change context to `<target>` |
| `H://cc <target>` | Hermes-native change context |
| `hermes://` | Default Hermes-agent runtime |
| `H://` | Global agentic domain for Hermes-agent |
| `NOUS://` | Nous Research provider/runtime |
| `llc://` | CLI LLC business/command surface |
| `daollc://` | DAO LLC governance / identity |
| `+æ://<name>` | Intent/permission token / DAO membership surface |
| `pc://` | Private client address / runtime |
| `pc://run <name>` | Run private client `<name>` via conductor |
| `vscode://` | VS Code control plane |
| `vscode://file/<path>` | Open file/folder in VS Code |
| `reachy://` | Reachy Mini robot surface |
| `mcp://` | MCP tools surface |
| `mcp://tools` | Tool runtime via MCP |
| `æ://` | Agentic-language-chassis context router |
| `æ://mesh` | Sovereign host list + liveness |
| `æ://gpu/<op>` | RTX 3050 compute |
| `æ://cc` | Command & control surface (human) |

**Routing priority:**
1. Backend: conductor dispatches schemes in `hermes_cli/conductor.py:_dispatch`
2. Bridge: `apps/reachy/app.py` exposes `/conductor`
3. Viewport HTML shell: send recognized schemes to `/conductor` with `{cmd, args}`

---

## 2. API Surface — VSCODER://BRIDGE Modules

The `VSCODER://BRIDGE` exposes six TypeScript modules over localhost WebSocket + JSON-RPC 2.0.

| Module | File | Responsibility |
|--------|------|----------------|
| `ipc.ts` | `src/bridge/ipc.ts` | JSON-RPC 2.0 over TCP, localhost-only, session auth (TTL 30 min), 64 KB payload cap |
| `state.ts` | `src/bridge/state.ts` | `IDEStateObserver` — `VSCODER_IDE_STATE_V1` versioned snapshots with compact deltas |
| `resolver.ts` | `src/bridge/resolver.ts` | `CommandResolver` — classifies effects as `LOCAL / DURABLE / EXTERNAL`; fail-closed (deny by default) |
| `plan.ts` | `src/bridge/plan.ts` | `PlanValidator` — workspace hash SHA-256, `409 PLAN_STATE_CONFLICT` on state drift |
| `capabilities.ts` | `src/bridge/capabilities.ts` | 11 typed capability namespaces (111+ capabilities total) |
| `events.ts` | `src/bridge/events.ts` | `EventStream` — compact deltas, full snapshots, reconnect/resync, secret exclusion |

### 2.1 `ipc.ts` — IPC/RPC Server

**Constants:**
- `MAX_PAYLOAD_SIZE = 64 * 1024` (64 KB)
- `DEFAULT_HOST = "127.0.0.1"` (localhost-only enforced)
- `DEFAULT_PORT = 0` (ephemeral, assigned at runtime)
- `SESSION_TTL_MS = 30 * 60 * 1000` (30 minutes)
- `JSONRPC_VERSION = "2.0"`

**JSON-RPC 2.0 Error Codes:**

| Code | Constant | Meaning |
|------|----------|---------|
| -32700 | `JSON_RPC_PARSE_ERROR` | Invalid JSON |
| -32600 | `JSON_RPC_INVALID_REQUEST` | Schema validation failure |
| -32601 | `JSON_RPC_METHOD_NOT_FOUND` | Method not registered |
| -32602 | `JSON_RPC_INVALID_PARAMS` | Parameters invalid |
| -32603 | `JSON_RPC_INTERNAL_ERROR` | Handler threw |
| -32000 | `JSON_RPC_SERVER_ERROR` | Server-side error |
| -32001 | `JSON_RPC_UNAUTHORIZED` | No valid session / no token |
| -32002 | `JSON_RPC_SESSION_EXPIRED` | Session TTL elapsed |
| -32003 | `JSON_RPC_SESSION_REVOKED` | Session explicitly revoked |
| -32004 | `JSON_RPC_PAYLOAD_TOO_LARGE` | Exceeds 64 KB |

**Security invariants:**
1. **Localhost-only binding** — server rejects any host other than `127.0.0.1` or `::1`.
2. **Connection possession ≠ authority** — a TCP connection grants nothing; authority comes per-session via token auth.
3. **Every message is validated** against the JSON-RPC 2.0 schema.
4. **Every message after auth must reference a valid, non-revoked session.**
5. **Payloads capped at 64 KB** — oversized messages rejected, connection closed.

**Public methods:** Only `auth.authenticate` is public. All other methods require a valid session.

**`IpcServer` API:**
- `start()` → `{ host, port }` — binds and starts listening
- `shutdown(timeoutMs = 5000)` — graceful shutdown; stops accepting, waits for pending requests
- `getConnectionCount()` / `getSessionCount()` / `getPendingRequestCount()`
- `registerHandler(method: string, handler: MethodHandler)` — register a JSON-RPC method handler

**Transport: localhost WebSocket / JSON-RPC 2.0** — newline-delimited JSON over TCP socket. Message framing is `\n`-delimited; messages exceeding 64 KB trigger `JSON_RPC_PAYLOAD_TOO_LARGE` and connection close.

### 2.2 `state.ts` — IDE State Observer

**Snapshot format:** `VSCODER_IDE_STATE_V1` (exported as `SNAPSHOT_VERSION` and `IDE_STATE_VERSION`).

| Field | Type | Description |
|-------|------|-------------|
| `version` | `"VSCODER_IDE_STATE_V1"` | Snapshot format version identifier |
| `timestamp` | `string` (ISO-8601) | When snapshot was taken |
| `workspace` | `{ folders, name, isTrusted }` | Workspace folders + trust state |
| `active_file` | `{ path, language, isDirty, isUntitled, scheme } \| null` | Active editor document |
| `open_editors` | `Array<{ path, language, isDirty, viewColumn }>` | All visible editors |
| `cursor` | `{ file, line, character } \| null` | Cursor position |
| `selection` | `{ file, start, end, isEmpty } \| null` | Current selection |
| `visible_ranges` | `Array<{ file, start, end }>` | Visible ranges across editors |
| `diagnostics` | `Array<{ file, message, severity, line, source? }>` | All workspace diagnostics |
| `terminals` | `Array<{ name, isBusy }>` | Active terminals |
| `running_tasks` | `Array<{ name, source }>` | Currently running tasks |
| `tests` | `{ controllers, totalTests }` | Test controller state |
| `debug_session` | `{ isActive, sessionId?, sessionType?, sessionName? }` | Debug session state |
| `breakpoints` | `Array<{ file, line, enabled, condition? }>` | All breakpoints |
| `scm_state` | `{ branch, changes, repositories }` | Git/SCM state |
| `current_branch` | `string` | Current git branch |
| `dirty_files` | `string[]` | Dirty (unsaved) file paths |
| `active_panel` | `string \| null` | Active panel (e.g. "terminal") |
| `focused_view` | `string \| null` | Currently focused view |

**State observer behavior:**
- `captureState()` — synchronous full snapshot of IDE state via VS Code APIs
- `refresh()` — recaptures state, fires `onDidChangeState` event
- `startObserving()` — subscribes to 13 native VS Code events (editor changes, document changes, debug sessions, breakpoints, tasks)
- `dispose()` — releases all subscriptions + event emitter

**Design principles:**
- Thin observer: subscribes to native VS Code events, maintains state, emits deltas. No routing intelligence.
- Compact deltas: only changed fields emitted, never full snapshots per keystroke.
- Full snapshot available on demand via `requestSnapshot()`.
- Secret exclusion: all state/events pass through `sanitize()`.
- Human-edit invalidation: human edits invalidate affected plans.
- Monotonic stateVersion: every event increments `stateVersion` by exactly 1.

### 2.3 `resolver.ts` — Command Resolver

**Entrypoints (5):**

| Entrypoint | minEffect | externalOnly | Description |
|------------|-----------|--------------|-------------|
| `terminal.run` | `LOCAL` | `false` | Run shell command in terminal |
| `task.run` | `LOCAL` | `false` | Run VS Code task |
| `ide.executeCommand` | `LOCAL` | `false` | Execute VS Code command |
| `scm.push` | `EXTERNAL` | `true` | SCM push operation |
| `ui.executeCommand` | `DURABLE` | `false` | UI command execution (never LOCAL) |

**Effect ordering:** `LOCAL` (0) < `DURABLE` (1) < `EXTERNAL` (2).

**Resolution algorithm:**
1. Look up entrypoint — deny if unknown (fail closed).
2. Look up command in `CAPABILITIES` registry — deny if unknown (fail closed).
3. If entrypoint is `externalOnly`, deny non-`EXTERNAL` commands.
4. Apply entrypoint's minimum effect (upgrade if necessary).
5. Return `Resolution` with `granted`, `requiresConfirmation`, `requiresPasskey`, and `reason`.

**Core invariants:**
1. `git.push` via any entrypoint (`terminal.run`, `task.run`, `ide.executeCommand`, `scm.push`) all resolve to `EXTERNAL`.
2. `ui.executeCommand(anything)` never resolves to `LOCAL`.
3. Unknown commands are denied (fail closed).
4. Authority follows effect, not entrypoint.

**`Resolution` object:**
- `entrypoint` — the entrypoint used
- `command` — the command invoked
- `capability` — the resolved `Capability` (name, effect, description)
- `effect` — final effect classification after entrypoint constraints
- `granted` — whether the command is known and allowed
- `requiresConfirmation` — `true` for DURABLE and EXTERNAL
- `requiresPasskey` — `true` for EXTERNAL only
- `reason` — human-readable explanation

### 2.4 `plan.ts` — Plan Validity Contract

A **plan** captures the expected workspace state at planning time. Before any mutation is applied, the current workspace state is compared against the plan's precondition. If divergence is detected, the mutation is rejected with `409 PLAN_STATE_CONFLICT`.

**Types:**
- `Hash` — SHA-256 hex digest (64 lowercase hex chars)
- `RelevantFile` — `{ path: string, hash: Hash }`
- `ExpectedState` — `{ workspaceHash, branch, head, dirtyState, relevantFiles[] }`
- `Plan` — `{ id, intent, expectedState, createdAt }`
- `CurrentState` — same shape as ExpectedState
- `ValidationResult` — `{ valid, reasons[], conflict? }`
- `PlanStateConflict` — `{ status: 409, code: "PLAN_STATE_CONFLICT", message, failedChecks[], planId, expected, current }`
- `ConflictKind` — `"WORKSPACE_HASH_MISMATCH" | "BRANCH_CHANGED" | "HEAD_CHANGED" | "DIRTY_STATE_CHANGED" | "RELEVANT_FILE_MUTATED"`

**PlanStateConflictError:** Extends `Error`, carries structured `PlanStateConflict` payload.

**PlanBuilder API:**
- `new PlanBuilder(intent, id?)` — constructor
- `.withGitState(branch, head, dirtyState)` — set git preconditions
- `.withRelevantFile(path, content|Buffer|string)` — add tracked file (hash computed automatically)
- `.withRelevantFileHash(path, hash)` — add tracked file with pre-computed hash
- `.withCreatedAt(timestamp)` — set creation time (defaults to now)
- `.build()` — validate required fields, compute `workspaceHash`, return `Plan`

**PlanValidator API:**
- `.validate(plan, current)` → `ValidationResult` (never throws)
- `.assertValid(plan, current)` — throws `PlanStateConflictError` if invalid

**Validation checks (in order):**
1. Branch match
2. HEAD match
3. Dirty-state match
4. Relevant-file hash match (detects missing, mutated, and new files)
5. Aggregate workspace hash match (catches anything above)

**Hashing:** `computeWorkspaceHash` sorts files by path, builds canonical JSON of `{ branch, head, dirtyState, files[] }`, then SHA-256s. `canonicalJson` sorts keys, no whitespace.

### 2.5 `capabilities.ts` — Typed IDE Capabilities Surface

**11 namespaces** with typed, serializable capability definitions:

| Namespace | Capabilities | Effect split |
|-----------|-------------|--------------|
| `workspace` | 18 | 16 LOCAL / 2 DURABLE |
| `editor` | 34 | 29 LOCAL / 5 DURABLE |
| `symbol` | 11 | 11 LOCAL / 1 DURABLE |
| `refactor` | 18 | 1 LOCAL / 17 DURABLE |
| `diagnostics` | 11 | 10 LOCAL / 1 DURABLE |
| `task` | 12 | 8 LOCAL / 4 DURABLE |
| `test` | 15 | 10 LOCAL / 5 DURABLE |
| `debug` | 22 | 14 LOCAL / 8 DURABLE |
| `terminal` | 15 | 8 LOCAL / 7 DURABLE |
| `scm` | 19 | 6 LOCAL / 13 DURABLE + 3 EXTERNAL |
| `ide` | 54 | 4 LOCAL / 50 DURABLE |

**Effect definitions:**
- `LOCAL` — no grant needed (read-only, in-memory, ephemeral)
- `DURABLE` — policy/confirmation required (persistent state changes)
- `EXTERNAL` — passkey + transaction-bound grant required (network, APIs)

**Key escape hatch:** `ide.executeCommand` is classified as `EXTERNAL` — it resolves through the command resolver (`resolver.ts`) rather than having a fixed effect.

**Registry API:**
- `CapabilityRegistry.register(cap)` / `.registerAll(caps[])`
- `.get(name)` / `.has(name)` / `.list()` / `.listByEffect(effect)` / `.listByNamespace(namespace)`
- `.size` — total registered count

**Global instances:** `capabilityRegistry` (singleton with all 111+ capabilities registered), `commandResolver` (singleton for `ide.executeCommand` escape hatch).

### 2.6 `events.ts` — Event Stream

**Delta kinds (`DeltaKind`):**
```
document.open | document.close | document.change | document.save
editor.selection | editor.visible | workspace.change | diagnostic
extension.activate | extension.deactivate | config.change
scm.change | debug.start | debug.stop | debug.breakpoint
task.start | task.end | test.start | test.end
human.edit
```

**DeltaEvent shape:**
- `stateVersion` — monotonically increasing (starts at 1)
- `kind` — one of `DeltaKind`
- `timestamp` — ISO-8601
- `uri?` — affected resource URI
- `language?` — language ID (document events)
- `changes?` — `TextChange[]` (document.change)
- `selection?` — `SelectionInfo`
- `visibleEditors?` — `string[]`
- `diagnostics?` — `DiagnosticSummary`
- `meta?` — sanitized metadata

**SnapshotEvent:** Full IDE state at a given `stateVersion` — the only place full document contents are emitted.

**Resync protocol:**
- Client sends `ResyncRequest { lastStateVersion, maxDeltas? }`
- If too far behind → returns `{ type: "snapshot", snapshot: SnapshotEvent }`
- If up to date → returns `{ type: "deltas", deltas: [], currentVersion }`
- Otherwise → returns `{ type: "deltas", deltas: DeltaEvent[], currentVersion }`
- History capped at `maxHistorySize` (default 1000)

**Secret exclusion (`sanitize`):**
- Strips values matching patterns: `password`, `passwd`, `secret`, `token`, `api[_-]?key`, `auth`, `credential`, `private[_-]?key`, `access[_-]?key`, `session[_-]?id`, `Bearer`, RSA private keys, JWTs, GitHub PATs (`ghp_`), OpenAI keys (`sk-`), Slack tokens (`xox[baprs]-`)
- Redacts sensitive keys: `password`, `passwd`, `secret`, `token`, `apiKey`, `api_key`, `auth`, `authorization`, `credential`, `credentials`, `privateKey`, `private_key`, `accessToken`, `access_token`, `refreshToken`, `refresh_token`, `sessionToken`, `session_token`, `idToken`, `id_token`, `clientSecret`, `client_secret`, `connectionString`, `connection_string`

**Delta integrity:**
- `hashDelta(delta)` — SHA-256 of canonical JSON (excluding timestamp)
- `verifyDeltaChain(deltas)` — checks monotonic stateVersion with no gaps

---

## 3. Bounds

### 3.1 Payload Cap

| Constant | Value | Enforced in |
|----------|-------|-------------|
| `MAX_PAYLOAD_SIZE` | 64 KB (65,536 bytes) | `ipc.ts` — per-connection buffer + per-message check |

Oversized messages trigger `JSON_RPC_PAYLOAD_TOO_LARGE` (-32004) and the connection is closed immediately.

### 3.2 Session TTL

| Constant | Value | Enforced in |
|----------|-------|-------------|
| `SESSION_TTL_MS` | 30 minutes (1,800,000 ms) | `ipc.ts` — `validateSession()` checks `expiresAt` |

Sessions expire at `Date.now() > session.expiresAt`. Expired sessions return `JSON_RPC_SESSION_EXPIRED` (-32002). Sessions can be revoked at any time without closing the connection (returns `JSON_RPC_SESSION_REVOKED` -32043).

**Grant TTL** (separate from session TTL): `GRANT_TTL_MS = 5 minutes` in `policy.ts` — per-operation grants expire independently.

### 3.3 Transport

| Property | Value |
|----------|-------|
| Protocol | JSON-RPC 2.0 over TCP (newline-delimited JSON) |
| Host | `127.0.0.1` (localhost only — enforced) |
| Port | Ephemeral (0) by default, configurable via `vscoderBridge.webmcpPort` (default 8123 for WebMCP HTTP) |
| Framing | `\n`-delimited messages |
| Auth | Token-based session authentication |

**Two transport layers coexist:**
1. **JSON-RPC 2.0 over TCP** — the `VSCODER://BRIDGE` IPC server (`ipc.ts`) — localhost-only, session-authenticated.
2. **HTTP/WebMCP** — the `WebMCPServer` in `extension.ts` — serves 9 tools (`vscoder_observe`, `vscoder_plan`, `vscoder_refactor`, `vscoder_build`, `vscoder_test`, `vscoder_debug`, `vscoder_benchmark`, `vscoder_git_diff`, `vscoder_receipt`) over HTTP on port 8123.

---

## 4. Authority Model (LOCAL / DURABLE / EXTERNAL)

Defined in `src/authority/policy.ts`. The PC:// authority model applies:

| Level | Grant Required | Passkey Required | Confirmation Required | Description |
|-------|---------------|-----------------|----------------------|-------------|
| **LOCAL** | No | No | No | Read-only, in-memory, ephemeral. No user interaction. |
| **DURABLE** | Yes | No | Yes | Persistent state changes. Policy/confirmation dialog. |
| **EXTERNAL** | Yes | Yes | Yes | Network, APIs, remote targets. Passkey + transaction-bound grant. |

**Classification rules (`assess`):**
- Targets using `file://`, `memory://`, `local://`, or `vscoder://` → LOCAL (unless write operation → DURABLE)
- Targets using `git://`, `durable://`, `fs://` (write), or `db://` → DURABLE
- Targets using `http://`, `https://`, `tcp://`, `udp://`, `dns://`, `smtp://`, `ftp://`, `ssh://`, `api://`, or unknown scheme → EXTERNAL

**Write operation detection (`isWriteOperation`):** Operations starting with `fs.write`, `fs.delete`, `fs.rename`, `fs.mkdir`, `fs.chmod`, `git.commit`, `git.push`, `git.merge`, `git.reset`, `db.insert`, `db.update`, `db.delete`, `durable.write`, `durable.update`, `durable.delete`.

**Grant management:**
- `requestGrant(operation, { passkeyId?, ttlMs? })` — creates a signed HMAC-SHA256 grant bound to the operation hash
- `verifyGrant(grant, expectedOperation)` — verifies expiry, operation binding, and HMAC signature (timing-safe compare)
- LOCAL grants have empty signatures (no verification needed)
- EXTERNAL grants require `passkeyId`; signature uses `signGrant(opHash, exp, passkeyId)`
- DURABLE grants use `"durable"` as the passkey namespace

**Credential resolution (`resolveCredential`):**
- `vault://<ref>` — look up in local credential store
- `env://<name>` — read from `process.env`
- Literal value — treated as-is (testing only)

**Capability invocation (`invokeCapability`):**
- Verifies grant against the operation before dispatching
- Returns `{ success, capability, output?, error? }` — never throws on failure

**Resolver-level authority:**
- `ui.executeCommand(anything)` never resolves to LOCAL (minimum DURABLE)
- `scm.push` via any entrypoint resolves to EXTERNAL
- Unknown commands are denied (fail closed)

---

## 5. VSCODER://BRIDGE Module Details

### 5.1 `ipc.ts` — JSON-RPC 2.0 IPC Server

**File:** `C:\æ\vscoder\src\bridge\ipc.ts`

```ts
const server = new IpcServer({
  host: "127.0.0.1",     // localhost-only enforced
  port: 0,               // ephemeral
  tokens: ["<auth-token>"], // at least one token required
  sessionTtlMs: 30 * 60 * 1000,  // 30 minutes
});
await server.start();  // → { host: "127.0.0.1", port: <assigned> }
```

**Session lifecycle:**
1. Client connects (no auth yet).
2. Client sends `auth.authenticate` with `{ token }`.
3. Server validates token (timing-safe compare via `crypto.timingSafeEqual`).
4. Session created: `{ id, connectionId, createdAt, expiresAt, revoked: false }`.
5. Session is bound to the connection; all subsequent messages on that connection reference the session.
6. Session expires after 30 minutes of inactivity (TTL from creation).
7. `auth.revoke` invalidates a session immediately without closing the connection.
8. `auth.session` returns current session metadata.

**Message validation (`validateJsonRpcSchema`):**
- `jsonrpc` must be `"2.0"`
- `method` must be a non-empty string
- `params` (if present) must be an object, not an array
- `id` (if present) must be string, number, or null
- Response messages must have either `result` or `error`, not both

### 5.2 `state.ts` — IDE State Observer

**File:** `C:\æ\vscoder-bridge\src\controllers\ideState.ts` (Phase 1) and `C:\æ\vscoder\src\bridge\state.ts` (Phase 2)

**Phase 2 `IDEStateObserver` (`state.ts`):**
- Constructor: `(context: vscode.ExtensionContext, options?: { maxHistorySize?, extensionVersion? })`
- `activate()` — subscribes to 20+ native VS Code events
- `deactivate()` — disposes all subscriptions
- `onDelta(handler)` / `onSnapshot(handler)` / `onPlanInvalidation(handler)` — handler registration
- `registerPlan(plan)` / `unregisterPlan(planId)` — plan tracking for human-edit invalidation
- `validatePlan(planId)` → `ValidationResult`
- `requestSnapshot()` → `IDEStateSnapshot` (full state with document contents)
- `currentStateVersion` — current monotonic version number

**VS Code events subscribed (Phase 2):**
- Documents: `onDidOpenTextDocument`, `onDidCloseTextDocument`, `onDidChangeTextDocument`, `onDidSaveTextDocument`, `onDidCreateFiles`, `onDidDeleteFiles`, `onDidRenameFiles`
- Workspace: `onDidChangeWorkspaceFolders`, `onDidChangeConfiguration`
- Editors: `onDidChangeActiveTextEditor`, `onDidChangeTextEditorSelection`, `onDidChangeVisibleTextEditors`, `onDidChangeTextEditorVisibleRanges`
- Diagnostics: `onDidChangeDiagnostics`
- SCM: `onDidOpenTextDocument`, `onDidSaveTextDocument` (refreshes SCM state)
- Debug: `onDidStartDebugSession`, `onDidTerminateDebugSession`, `onDidChangeBreakpoints`
- Tasks: `onDidStartTask`, `onDidEndTask`
- Tests: `onDidChangeTestResults`
- Extensions: `onDidChangeExtensions`

**Human-edit detection:** If `doc.version > lastKnownVersions.get(uri) + 1`, the edit is flagged as human-originated. Affected plans are validated and invalidated if state drifted.

### 5.3 `resolver.ts` — Command Resolver

**File:** `C:\æ\vscoder\src\bridge\resolver.ts`

**Capability registry:** 30 commands across git, filesystem, build/test/debug, refactoring, symbols, diagnostics, network, benchmark, and receipts.

| Command | Effect | Description |
|---------|--------|-------------|
| `git.push` | EXTERNAL | Push commits to remote |
| `git.commit` | DURABLE | Commit changes to local repository |
| `git.diff` | LOCAL | Show diff of changes |
| `git.status` | LOCAL | Show working tree status |
| `git.branch` | DURABLE | Create or switch branches |
| `git.merge` | DURABLE | Merge branches |
| `git.reset` | DURABLE | Reset current branch |
| `git.clone` | EXTERNAL | Clone remote repository |
| `git.fetch` | EXTERNAL | Fetch from remote |
| `git.pull` | EXTERNAL | Pull from remote |
| `fs.read` | LOCAL | Read file contents |
| `fs.write` | DURABLE | Write file contents |
| `fs.delete` | DURABLE | Delete file |
| `fs.rename` | DURABLE | Rename file |
| `build.run` | LOCAL | Run build task |
| `test.run` | LOCAL | Run tests |
| `debug.start` | LOCAL | Start debug session |
| `refactor.apply` | DURABLE | Apply refactoring |
| `refactor.list` | LOCAL | List available refactorings |
| `symbol.find` | LOCAL | Find symbol definition |
| `symbol.references` | LOCAL | Find symbol references |
| `symbol.rename` | DURABLE | Rename symbol |
| `workspace.symbols` | LOCAL | Search workspace symbols |
| `diagnostics.read` | LOCAL | Read diagnostics |
| `http.fetch` | EXTERNAL | HTTP request |
| `benchmark.run` | LOCAL | Run benchmark |
| `receipt.generate` | DURABLE | Generate receipt |
| `receipt.verify` | LOCAL | Verify receipt chain |

### 5.4 `plan.ts` — Plan Validity Contract

**File:** `C:\æ\vscoder\src\bridge\plan.ts`

Self-contained — uses only Node.js `crypto` built-in. No external dependencies.

**409 PLAN_STATE_CONFLICT flow:**
1. `PlanBuilder` captures expected state (git branch/HEAD, dirtiness, per-file SHA-256 hashes, aggregate workspace hash).
2. Before mutation, `captureCurrentState()` computes the same metrics from live VS Code state.
3. `PlanValidator.validate()` compares expected vs. current, producing a structured `PlanStateConflict` with `failedChecks[]`.
4. `assertValid()` throws `PlanStateConflictError` for mutation code paths that need rejection.

**Workspace hash computation:**
```
canonicalJson({ branch, head, dirtyState, files: sorted(relevantFiles) }) → sha256()
```

### 5.5 `capabilities.ts` — Typed IDE Capabilities

**File:** `C:\æ\vscoder\src\bridge\capabilities.ts`

**11 capability namespaces** (111+ typed `CapabilityDefinition` entries):

| Namespace | Count | Key Operations |
|-----------|-------|---------------|
| `workspace` | 18 | readFile, writeFile, listFiles, findFiles, applyEdit, getConfiguration, updateConfiguration |
| `editor` | 34 | openDocument, editDocument, insertSnippet, setSelection, executeFormatDocument, executeCodeActionProvider, executeCompletionItemProvider |
| `symbol` | 11 | find, references, rename, workspaceSymbols, definition, typeDefinition, implementation, hover, documentSymbols |
| `refactor` | 18 | list, apply, extractMethod, extractFunction, extractVariable, extractConstant, moveToNewFile, organizeImports, inlineVariable, convertToAsync, convertToArrow, addJSDoc, removeUnused |
| `diagnostics` | 11 | read, getForUri, getForEditor, clear, getSeverityCount, getErrors, getWarnings, getHints, getInformation |
| `task` | 12 | run, fetch, getDefaultBuildTask, terminate, restart, getActiveTasks, registerTaskProvider |
| `test` | 15 | run, target, coverage, createController, getControllers, getTestItem, createRunProfile, runTestsFromProfile |
| `debug` | 22 | start, stop, inspect, addBreakpoint, continue, stepInto, stepOver, stepOut, evaluate, getStackFrames, getScopes, getVariables |
| `terminal` | 15 | run, create, sendText, show, hide, dispose, getActive, getAll, getByName, registerTerminalProfileProvider |
| `scm` | 19 | status, diff, branch, commit, push, pull, fetch, stage, unstage, discard, createBranch, checkout, merge, rebase, reset, createPatch, applyPatch |
| `ide` | 54 | executeCommand, getConfiguration, showInformationMessage, showWarningMessage, showErrorMessage, showQuickPick, showInputBox, createWebviewPanel, createTerminal, createOutputChannel, registerCommand, registerTextEditorCommand, createTreeView, createStatusBarItem |

### 5.6 `events.ts` — Event Stream

**File:** `C:\æ\vscoder\src\bridge\events.ts`

Self-contained — uses only Node.js `crypto` built-in.

**EventStream lifecycle:**
- `onDelta(listener)` → unsubscribe function
- `onSnapshot(listener)` → unsubscribe function
- `requestSnapshot()` → `SnapshotEvent` (full IDE state)
- `resync({ lastStateVersion, maxDeltas? })` → `ResyncResponse`

**Delta history:** capped at `maxHistorySize` (default 1000 entries). When exceeded, oldest deltas are dropped.

---

## 6. Activation Events

Defined in `package.json` for both the VSCODER extension (`C:\æ\vscoder\package.json`) and the VSCODER://BRIDGE extension (`C:\æ\vscoder-bridge\package.json`):

### 6.1 VSCODER Extension (`vscoder`)

```json
"activationEvents": [
  "onUri",
  "onStartupFinished",
  "onCommand:vscoder.open",
  "onCommand:vscoder.observe",
  "onCommand:vscoder.plan",
  "onCommand:vscoder.refactor",
  "onCommand:vscoder.build",
  "onCommand:vscoder.test",
  "onCommand:vscoder.debug",
  "onCommand:vscoder.benchmark",
  "onCommand:vscoder.gitDiff",
  "onCommand:vscoder.receipt"
]
```

### 6.2 VSCODER://BRIDGE Extension (`vscoder-bridge`)

```json
"activationEvents": [
  "onUri",
  "onStartupFinished",
  "onCommand:vscoderBridge.open",
  "onCommand:vscoderBridge.observe",
  "onCommand:vscoderBridge.plan",
  "onCommand:vscoderBridge.refactor",
  "onCommand:vscoderBridge.build",
  "onCommand:vscoderBridge.test",
  "onCommand:vscoderBridge.debug",
  "onCommand:vscoderBridge.benchmark",
  "onCommand:vscoderBridge.gitDiff",
  "onCommand:vscoderBridge.receipt"
]
```

**Rule:** Every command must have its own `onCommand:` activation event entry, plus `onUri` (for `vscode://` URI dispatch) and `onStartupFinished`. Do **not** rely on `onStartupFinished` alone — it loads the extension on every VS Code startup regardless of need.

### 6.3 Command Registration Tuple (4-part wiring)

Every Hermes webview/dispatch command requires:
1. `package.json` contribution entry (under `contributes.commands`)
2. `registerCommand('vscoderBridge.xyz')` constant in `extension.ts`
3. `context.subscriptions.push(disposable)` registration
4. `renderXxx()` exported/reachable symbol in scope

Omitting any one part produces silent failures.

---

## 7. Webview HTML Helpers

### 7.1 Gold-on-Void Design System (canonical webview skin)

**Reference implementation:** `renderGoldShell(title, bodyHtml, { script })` in `vscode-remote-use/src/extension.ts` (v0.3.0).

**CSS tokens:**

```css
:root {
  --void: #050505;        /* background */
  --panel: #0b0b0b;       /* panel background */
  --gold: #D4AF37;        /* primary gold */
  --gold-glow: rgba(212,175,55,.32);
  --neon: #00ffa3;        /* emerald accent */
  --ink: #e6e6e6;         /* primary text */
  --muted: #8b8b8b;       /* secondary text */
  --border: rgba(212,175,55,.22);
  --border-hot: rgba(212,175,55,.5);
}
```

**Typography:** `Orbitron` (display headings), `JetBrains Mono` (body/monospace).

**Visual elements:**
- Scanlines via fixed `::before` gradient
- Sharp edges (border-radius: 8px on panels)
- `#hermiphicationisinevitable` hash footer on every surface

**Rule:** When adding a new webview, call `renderGoldShell(...)` — do NOT inline a one-off `<style>` with a different palette. Grep compiled output for `#0e1116` (GitHub-dark drift) — must be 0.

### 7.2 homeOS Surface Fallback Chain

`renderHomeOS()` must prefer surfaces in this order:

1. `templates/agentic.html` — repo file-backed surface (first preference)
2. Configurable fallback surface path — user-defined override
3. Embedded deterministic fallback HTML — in-memory HTML if no file
4. Ephemeral no-op HTML — rendered when all else unavailable (never crash)

**Surface button grammar (homeOS surface):**
- `terminal` · Hermes terminal profile
- `editor` · VS Code editor control
- `files` · Bounded filesystem primitive
- `victus` · Victus machine vitals
- `nvidia` · NVIDIA GPU C2
- `vlc` · VLC fleet command
- `ffmpeg` · FFmpeg media pipeline
- `qr` · QR-tagged HTML execution
- `mesh` · Bounded sovereign mesh
- `shell` · agentic.html viewport

**Dispatcher handling:**
- Known `remoteUse.*` local dispatch
- Fallback to `vscode.commands.executeCommand()` for unknown commands
- No-op instead of crashing for unknown subsurfaces

### 7.3 Webview Message Safety

**Never call webview message handlers from other handlers.** Use `vscode.commands.executeCommand(...)` to repost to the registered command. This preserves activation state.

**Incorrect:**
```ts
case 'remoteUse.htmlSurface': await openHtmlSurface();
```

**Correct:**
```ts
case 'remoteUse.htmlSurface': await vscode.commands.executeCommand('remoteUse.htmlSurface');
```

### 7.4 Extension-Side Webview Messaging

Local webviews may run outside VS Code webview host. Guard creator APIs defensively:

```js
const vscode = typeof acquireVsCodeApi !== 'undefined' ? acquireVsCodeApi() : null;
if (vscode) {
  window.addEventListener('message', (event) => {
    const message = event && event.data;
    if (!message || !message.command) return;
    if (message.command === 'remoteUse.webLLM') fakeInference();
  });
}
```

### 7.5 VSCODER://BRIDGE Webview HTML

**File:** `C:\æ\vscoder-bridge\src\extension.ts` (lines 398–537) and `C:\æ\vscoder\webview/index.html`

The bridge serves an embedded HTML surface at the root (`/` or `/index.html`) with:
- Gold-on-void design system
- Instruction textarea + 9 tool buttons
- Live capability graph (14 cards)
- Output panel + receipt/log display
- Status bar with hash chain display

**Agent panel webview** (`getAgentPanelHtml`):
- Minimalist gold-on-void theme
- Instruction textarea
- 9 tool buttons (Observe, Plan, Refactor, Build, Test, Debug, Benchmark, Git Diff, Receipt)
- Output `<pre>` element
- `acquireVsCodeApi()` messaging bridge for VS Code integration

**Trust gating rule:**
- Display-only preview can work before trust
- Context injection, command dispatch, agent session actions, and webview messaging still require trust
- When Restricted Mode is active, target the integrated browser first, then surface the explicit trust/approval path

---

## 8. Code Mode Integration (F10 → :æcode: → Sandboxed Python)

### 8.1 Architecture

```
Model → Python code against æ DSL → æ_code_mode.py sandbox → VS Code APIs
                                    (or VSCODER://BRIDGE /bridge/codemode.ts)
```

**Two substrates:**

| Substrate | File | Language | Sandbox mechanism |
|-----------|------|----------|-------------------|
| Python sandbox | `C:\æ\agents\æ_code_mode.py` | Python | `exec()` with restricted globals dict |
| TypeScript substrate | `C:\æ\vscoder\src\bridge\codemode.ts` | JavaScript/TypeScript | `new Function()` with restricted params |

The model writes code against the `æ` DSL namespace. It is executed in a sandbox with explicit bindings, no filesystem/network/process access by default, and a configurable timeout (default 30s).

### 8.2 Trigger

**F10 → `:æcode:` → sandboxed Python:**
1. User presses F10 in VS Code
2. Enters `:æcode:` command mode
3. Model writes Python code against the `æ` DSL
4. Code is passed to `æ_code_mode.py` for sandboxed execution
5. Output returned to VS Code (webview or panel)

For the TypeScript substrate, `CodeModeExecutor.execute(code)` compiles the code via `new Function('æ', 'json', 'Math', 'Date', 'console', ...)` and runs it with a timeout race.

### 8.3 Sandboxed Globals

**Pre-bound globals (Python sandbox — `æ_code_mode.py`):**

| Global | Type | Description |
|--------|------|-------------|
| `æ` | `_Æ` | The æ namespace object (all bindings) |
| `json` | module | JSON serialization |
| `re` | module | Regular expressions |
| `datetime` | module | Date/time |
| `time` | module | Time (incl. `time.sleep`) |
| `hashlib` | module | SHA-256 hashing |
| `urllib` | module | HTTP (restricted: only `urllib.request`) |
| `Path` | class | `pathlib.Path` (limited use) |
| `Exception` | class | |
| `ValueError` | class | |
| `TypeError` | class | |
| `KeyError` | class | |
| `IndexError` | class | |

**Allowed modules (Python):** `json, re, datetime, urllib, collections, typing, dataclasses, enum, math, hashlib, subprocess, os`

**Blocked builtins:** `open, socket, subprocess, os.system, exec, eval, compile, __import__, input, breakpoint, execfile`

**`__import__` guard:** The sandbox explicitly blocks `__import__` via `BLOCKED_BUILTINS`. Sandboxed code **must use pre-bound globals only** — it cannot import new modules. Any attempt to call `__import__('module')` raises `PermissionError`. This prevents escaping the sandbox via `import os` or `import socket`.

### 8.4 Code Mode Bindings (`æ` namespace)

#### `æ.storage` — Storage bindings

| Method | Signature | Description |
|--------|-----------|-------------|
| `storage.read` | `(path: str) → str` | Read file contents as UTF-8 text |
| `storage.write` | `(path: str, content: str) → { ok, path, bytes }` | Write content to file |
| `storage.list` | `(dir: str) → str[]` | List filenames in a directory |

**Python sandbox:** Uses `Path` directly (sandboxed, no `open()` builtin — uses `Path.read_text()` / `Path.write_text()`).

**TypeScript substrate:** No storage binding exposed — TypeScript code accesses `vscode.workspace.fs` directly.

#### `æ.keeper` — Keeper bindings (audit, ledger, publish, remember, recall)

| Method | Signature | Description |
|--------|-----------|-------------|
| `keeper.audit` | `(target: str) → { verdict, evidence[] }` | Scan a resource for issues |
| `keeper.reconcile` | `(a: str, b: str) → { match, diff[] }` | Compare two sources |
| `keeper.ledger` | `(entry: dict) → str` | Append-only ledger write with SHA-256 signature |
| `keeper.publish` | `(facts: str) → { published, sig }` | Publish to æ.social receipts network |
| `keeper.remember` | `(fact: str) → str` | Store a fact in the ledger |
| `keeper.recall` | `(query="", limit=50) → { matches[] }` | Retrieve facts from ledger |
| `keeper.handoff` | `(to: str, task: str) → { ok, to, task }` | Delegate work to another bot |

**Evidence requirement:** `keeper.ledger()` and `keeper.publish()` **require** an `evidence` field — a claim without proof is refused (`ValueError`).

**Audit targets (Python sandbox):** `broker` (probes `http://129.212.180.252:3000/`), `ide`/`workspace` (delegates to TypeScript substrate), others return `unknown`.

**TypeScript substrate (`KeeperBindings`):**
- `keeper.audit('ide' | 'workspace')` — checks diagnostics count, workspace folder count
- `keeper.audit('git')` — checks git branch presence
- `keeper.ledger(entry)` — requires `entry.evidence`, requests `DURABLE` grant, returns 16-char hash
- `keeper.publish(facts)` — requests `EXTERNAL` grant, returns `{ published, sig }`
- `keeper.remember(fact)` — delegates to `ledger({ kind: 'fact', text, evidence: 'user-provided' })`
- `keeper.recall(query, limit)` — returns `{ matches: [] }` (stub)

#### `æ.mesh` — Mesh bindings

| Method | Signature | Description |
|--------|-----------|-------------|
| `mesh.bots` | `() → MeshBot[]` | List active mesh bots |
| `mesh.read` | `(bot_id: str) → BotState` | Read a bot's state |
| `mesh.write` | `(bot_id: str, key: str, value) → WriteResult` | Write state to a bot (requires DURABLE grant) |

**Known bots (4):**
| ID | Status | Tier |
|----|--------|------|
| `hermes-agent` | ok | 0 |
| `vps_node` | ok | 1 |
| `teknium` | ok | 2 |
| `keeper` | ok | 3 |

#### `æ.social` — æ.social bindings

| Method | Signature | Description |
|--------|-----------|-------------|
| `social.post` | `(value: dict) → { ok, sig }` | Publish a post to the receipts network |

**Required fields:** `text`, `kind`, `agent`, `principal` — **evidence is required** (a post without proof is refused `ValueError`).

**Post target:** `http://129.212.180.252:3000/xrpc/ae.vps.record` (æ.social receipts network).

#### `æ.rtx` — RTX bindings

| Method | Signature | Description |
|--------|-----------|-------------|
| `rtx.probe` | `() → { gpu, temp, util, mem_used, mem_total }` | GPU telemetry via `nvidia-smi` |
| `rtx.compute` | `(op: str) → { ok, op, result }` | GPU compute operation |

#### `æ.video` — Vidæo bindings

| Method | Signature | Description |
|--------|-----------|-------------|
| `video.render` | `(scene, seconds=5, out="") → dict` | Render via æRTXrender (NVENC/NVENC) |
| `video.verify` | `(video_path) → dict` | Verify with SupervisorVideo (luminance, contrast, motion, black frames) |
| `video.receipt` | `(video_path, intent, prev="") → dict` | SHA-256 receipt chain entry |
| `video.status` | `()` | Toolchain status |

#### `æ.vps` — VPS bindings

| Method | Signature | Description |
|--------|-----------|-------------|
| `vps.status` | `() → { vps, uptime }` | Broker health (probes `http://129.212.180.252:3000/`) |
| `vps.up` | `(resource: str)` | Provision a resource |
| `vps.down` | `(resource: str)` | Deprovision a resource |
| `vps.logs` | `(resource: str, lines=50)` | Get logs (simulated) |

### 8.5 TypeScript `AENamespace` (`æ` in TS substrate)

Defined in `codemode.ts` — three binding groups:

| Interface | Methods | Effect |
|-----------|---------|--------|
| `MeshBinding` | `bots()`, `read(botId)`, `write(botId, key, value)` | read=LOCAL, write=DURABLE |
| `KeeperBinding` | `audit(target)`, `reconcile(a,b)`, `ledger(entry)`, `handoff(to,task)`, `publish(facts)`, `remember(fact)`, `recall(query, limit)` | ledger/publish=EXTERNAL, audit/reconcile/remember/recall=LOCAL |
| `IdeBinding` | `openFile(path)`, `getDiagnostics()`, `runTask(name)`, `executeCommand(cmd, ...args)`, `getState()` | openFile=LOCAL, runTask=DURABLE, executeCommand=resolved via CommandResolver |

### 8.6 Execution Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| No `open()`/`import`/`eval`/`exec` | `_SandboxedBuiltins` dict removes blocked builtins; `__import__` raises `PermissionError` |
| Conflict marker rejection | Structure gate: `<<<<<<<` / `>>>>>>>` in code → `CONFLICT MARKERS IN CODE — structure gate rejected` |
| Timeout | 30-second budget (configurable); thread-based kill; exit code 124 on timeout |
| Audit logging | Every call logged to `~/.hermes/logs/code_mode.log` with `ts`, `code_hash`, `elapsed_ms`, `result_preview` |
| Ledger integrity | SHA-256 signature appended to every ledger entry (`hashlib.sha256(json.dumps(entry, sort_keys=True))`) |

**Sandbox test suite (10 checks, `æ_code_mode.py --test`):**

| # | Test | Verifies |
|---|------|----------|
| 1 | `open('/etc/passwd')` | Blocks `open()` |
| 2 | `import socket` | Blocks `socket` import |
| 3 | `æ.mesh.bots()` | Returns 4 bots |
| 4 | `æ.keeper.ledger(...)` without evidence | Requires evidence |
| 5 | `æ.keeper.ledger(...)` with evidence | Returns 16-char sig |
| 6 | `æ.social.post(...)` without evidence | Requires evidence |
| 7 | `æ.social.post(...)` with evidence | Returns 16-char sig |
| 8 | `æ.keeper.audit('broker')` | Returns verdict in ok/issues/down |
| 9 | `time.sleep(60)` with 2s timeout | Kills long code (exit 124) |
| 10 | `æ.storage.write/read` roundtrip | Read/write works |

**TypeScript `test-codemode.cjs` test suite (5 checks):**

| # | Test | Verifies |
|---|------|----------|
| 1 | `æ.mesh.bots()` | Returns 4 bots |
| 2 | `æ.keeper.audit('ide')` + `æ.keeper.ledger(...)` | Audit + ledger composition |
| 3 | `try/catch` sandbox isolation | Sandbox isolated + arithmetic |
| 4 | 3-link ledger chain | Receipt chain linking |
| 5 | `æ.keeper.ledger(...)` without evidence | Evidence gate enforced |

---

## 9. Toolchain

### 9.1 VS Code Extension Build

```bash
# vscoder extension (C:\æ\vscoder)
cd C:\æ\vscoder
npm install        # install deps
npm run compile    # tsc -p ./ (compiles to out/)
npm run package    # vsce package → VSCODER-*.vsix

# vscoder-bridge extension (C:\æ\vscoder-bridge)
cd C:\æ\vscoder-bridge
npm install
npm run compile
npm run package    # vsce package → vscoder-bridge-*.vsix
```

**tsconfig.json:** CommonJS module, ES2022 target, strict mode, source maps, rootDir=`src`, outDir=`out`.

### 9.2 Package Metadata

| Field | vscoder | vscoder-bridge |
|-------|---------|-----------------|
| name | `vscoder` | `vscoder-bridge` |
| displayName | `VSCODER://` | `VSCODER://BRIDGE` |
| publisher | `vscoder` | `vscoder` |
| version | `0.1.0` | `1.0.0` |
| engines.vscode | `^1.85.0` | `^1.85.0` |
| main | `./out/extension.js` | `./out/extension.js` |
| categories | Other, AI, ML | Other, AI, ML |
| icon | `images/icon.svg` | `images/icon.svg` |

### 9.3 Python Sandbox (standalone)

```bash
# Run inline code
python æ_code_mode.py --eval "print(æ.mesh.bots()[0]['id'])"

# Run a .py file
python æ_code_mode.py script.py

# Run tests
python æ_code_mode.py --test
```

### 9.4 Node Toolchain Paths (Python sandbox video bindings)

| Tool | Path |
|------|------|
| Node | `C:/Users/yaelm/AppData/Local/hermes/tools/node-26.7.0-win32-x64/node.exe` |
| render.mjs | `C:/æ/threejs-curriculo/render.mjs` |
| vidæo.py | `C:/æ/vidæo/vidæo.py` |
| GPU Python | `C:/gpu/Scripts/python.exe` |
| ffmpeg (NVENC) | `C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-7.1-nvenc/bin/ffmpeg.exe` |

### 9.5 VSIX Packaging Rules

- The extension is native Hermes product code — `vscode-remote-use/` lives inside the `hermes-fork` directory.
- Shipping identity: `publisher: "hermes-agent"` (installed as `hermes-agent.hermes-agent-<version>`).
- After packaging, verify VSIX exists and measure size + SHA256 with Python stdlib.
- Update `RELEASE_MANIFEST.md` artifact block.
- Exclude VSIX filenames from opensourceware boundary docs (build metadata, not source).

---

## 10. Activation Events (Detail)

The `onUri` activation event handles `vscode://` URI dispatch. The extension's `activate()` function:

1. Creates `IpcServer` with auth token from config
2. Starts the WebMCP HTTP server (port 8123 by default)
3. Registers all command handlers via `context.subscriptions.push()`
4. Initializes receipt chain
5. Initializes IDE state observer
6. Logs activation to receipt chain

**Important:** `onStartupFinished` alone loads the extension on every VS Code startup regardless of need. Always add `onUri` and `onCommand:<cmd>` for each exposed command.

---

## 11. Receipt System (SHA-256 Hash Chain)

Defined in `src/receipts/witness.ts`.

**ReceiptEntry:**
- `seq` — sequence number (1-based)
- `timestamp` — ISO-8601
- `action` — what was performed
- `input` — trimmed to 500 chars
- `output` — trimmed to 500 chars
- `prevHash` — hash of previous entry (`'genesis'` for first)
- `hash` — SHA-256 of `{ seq, timestamp, action, input, output, prevHash }`

**Verification:** Each receipt's hash is recomputed and compared. Each entry's `prevHash` must match the previous entry's `hash`. The chain is only valid if all links verify.

**Code Mode audit logging** (`æ_code_mode.py`):
- Log file: `~/.hermes/logs/code_mode.log`
- Each entry: `{ ts, code_hash, elapsed_ms, result_preview }`
- `code_hash` = SHA-256 of the executed code (truncated to 16 chars)

---

## 12. HomeOS Surface Fallback Chain (Detail)

`renderHomeOS()` preference order (from `vscode-as-skill` skill):

1. **`templates/agentic.html`** — `C:\æ\site\agentic.html` (repo file-backed surface). Renders the gold-on-void agentic viewport with mesh canvas, command prompt, capability pills, and install panel.
2. **Configurable fallback surface path** — `remoteUse.hermesRepoPath` / `remoteUse.vlcPath` / `remoteUse.daoSurfacePath` from VS Code settings. Falls back to `vscode.workspace.workspaceFolders?.[0]?.uri.fsPath` when blank.
3. **Embedded deterministic fallback HTML** — `renderGoldShell(title, bodyHtml, { script })` from `vscode-remote-use/src/extension.ts` (v0.3.0). Uses canonical gold-on-void tokens.
4. **Ephemeral no-op HTML** — rendered when all surfaces unavailable. Never crashes.

**Gold-on-void design system** (canonical tokens enforced across all Hermes webviews):
- Void `#050505`, Gold `#D4AF37`, Neon/Emerald `#00ffa3`, Orbitron + JetBrains Mono, sharp edges, scanlines
- `#hermiphicationisinevitable` hash footer on every surface
- Rule: call `renderGoldShell(...)` for new webviews; do NOT inline one-off `<style>` blocks

---

## 13. Scheme Coverage: vscode:// sub-routes

| Route | Description | Handler |
|-------|-------------|---------|
| `vscode://` | Control plane entry | `vscode.openFolder` / editor actions |
| `vscode://file/<path>` | Open file/folder | `vscode.openFolder` / `vscode.open` |
| `vscode://mesh` | Sovereign mesh liveness | `remoteUse.mesh` / mesh controller |
| `vscode://gpu` | GPU compute surface | `remoteUse.nvidia` / RTX 3050 bridge |
| `vscode://secrets` | Local secret storage | `~/.hermes/.env` + `secrets.sources` |
| `vscode://cc` | Command & control | `:æcode:` / Code Mode substrate |
| `vscode://home` | homeOS hub | `renderHomeOS()` fallback chain |

---

*Document generated from live source files: `C:\æ\vscoder\src\bridge\*.ts`, `C:\æ\vscoder-bridge\src\*.ts`, `C:\æ\agents\æ_code_mode.py`, `C:\æ\vscoder\package.json`, `C:\æ\vscoder-bridge\package.json`, `C:\æ\AGENTS.md`.*
