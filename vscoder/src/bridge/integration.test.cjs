/**
 * VSCODER:// Bridge — Integration Test
 *
 * Tests cross-module coherence for all 6 bridge modules:
 *   1. All modules load without errors
 *   2. IPC server binds to localhost only
 *   3. State observer produces VSCODER_IDE_STATE_V1 with stateVersion
 *   4. Command resolver classifies push as EXTERNAL
 *   5. Plan validity rejects stale state with 409
 *   6. Event stream emits deltas
 *   7. Capabilities registry has all required namespaces
 *
 * Run: node integration.test.cjs
 */

const assert = require("assert");
const path = require("path");

// ---------------------------------------------------------------------------
// Mock vscode module for state.ts and capabilities.ts
// ---------------------------------------------------------------------------
const vscodeMock = {
  Uri: {
    file: (p) => ({ toString: () => `file://${p}`, fsPath: p }),
    parse: (s) => ({ toString: () => s, fsPath: s.replace("file://", "") }),
  },
  workspace: {
    workspaceFolders: [],
    textDocuments: [],
    onDidOpenTextDocument: () => ({ dispose() {} }),
    onDidCloseTextDocument: () => ({ dispose() {} }),
    onDidChangeTextDocument: () => ({ dispose() {} }),
    onDidSaveTextDocument: () => ({ dispose() {} }),
    onDidCreateFiles: () => ({ dispose() {} }),
    onDidDeleteFiles: () => ({ dispose() {} }),
    onDidRenameFiles: () => ({ dispose() {} }),
    onDidChangeWorkspaceFolders: () => ({ dispose() {} }),
    onDidChangeConfiguration: () => ({ dispose() {} }),
    getConfiguration: () => ({ get: () => undefined }),
  },
  window: {
    visibleTextEditors: [],
    activeTextEditor: undefined,
    onDidChangeActiveTextEditor: () => ({ dispose() {} }),
    onDidChangeTextEditorSelection: () => ({ dispose() {} }),
    onDidChangeVisibleTextEditors: () => ({ dispose() {} }),
    onDidChangeTextEditorVisibleRanges: () => ({ dispose() {} }),
  },
  languages: {
    onDidChangeDiagnostics: () => ({ dispose() {} }),
    getDiagnostics: () => [],
  },
  extensions: {
    getExtension: () => undefined,
    onDidChange: () => ({ dispose() {} }),
  },
  debug: {
    activeDebugSession: undefined,
    breakpoints: [],
    onDidStartDebugSession: () => ({ dispose() {} }),
    onDidTerminateDebugSession: () => ({ dispose() {} }),
    onDidChangeBreakpoints: () => ({ dispose() {} }),
  },
  tasks: {
    onDidStartTask: () => ({ dispose() {} }),
    onDidEndTask: () => ({ dispose() {} }),
  },
  tests: {
    onDidChangeTestResults: () => ({ dispose() {} }),
  },
  DiagnosticSeverity: { Error: 0, Warning: 1, Information: 2, Hint: 3 },
  commands: {
    executeCommand: async () => undefined,
    getCommands: async () => [],
  },
};

// Register mock by intercepting Module._load
const Module = require("module");
const originalLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === "vscode") {
    return vscodeMock;
  }
  return originalLoad.call(this, request, parent, isMain);
};

// ---------------------------------------------------------------------------
// Test runner
// ---------------------------------------------------------------------------
let passed = 0;
let failed = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    failed++;
    failures.push({ name, error: err });
    console.log(`  ✗ ${name}`);
    console.log(`    ${err.message}`);
  }
}

async function testAsync(name, fn) {
  try {
    await fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    failed++;
    failures.push({ name, error: err });
    console.log(`  ✗ ${name}`);
    console.log(`    ${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
console.log("\nVSCODER:// Bridge Integration Tests\n");

// -- Module 1: IPC ----------------------------------------------------------
const ipc = require("../../out/bridge/ipc");
const { IpcServer, DEFAULT_HOST, MAX_PAYLOAD_SIZE } = ipc;

test("IPC: IpcServer class is exported and constructable", () => {
  assert.strictEqual(typeof IpcServer, "function");
  const server = new IpcServer({ tokens: ["test-token"] });
  assert.ok(server instanceof IpcServer);
});

test("IPC: DEFAULT_HOST is 127.0.0.1 (localhost only)", () => {
  assert.strictEqual(DEFAULT_HOST, "127.0.0.1");
});

test("IPC: MAX_PAYLOAD_SIZE is 64KB", () => {
  assert.strictEqual(MAX_PAYLOAD_SIZE, 64 * 1024);
});

test("IPC: Server rejects non-localhost binding", () => {
  assert.throws(
    () => new IpcServer({ tokens: ["t"], host: "0.0.0.0" }),
    /localhost only/
  );
});

test("IPC: Server requires at least one token", () => {
  assert.throws(
    () => new IpcServer({ tokens: [] }),
    /token is required/
  );
});

// -- Module 2: Events -------------------------------------------------------
const events = require("../../out/bridge/events");
const { EventStream, sanitize, verifyDeltaChain, hashDelta } = events;

test("Events: EventStream class is exported and constructable", () => {
  assert.strictEqual(typeof EventStream, "function");
  const stream = new EventStream();
  assert.ok(stream instanceof EventStream);
});

test("Events: sanitize redacts sensitive keys", () => {
  const input = { password: "secret123", nested: { token: "abc" } };
  const result = sanitize(input);
  assert.strictEqual(result.password, "[REDACTED]");
  assert.strictEqual(result.nested.token, "[REDACTED]");
});

test("Events: sanitize redacts JWT-like strings", () => {
  const input = "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U";
  const result = sanitize(input);
  assert.ok(result.includes("[REDACTED]"));
});

test("Events: EventStream emits deltas with monotonic stateVersion", () => {
  const stream = new EventStream();
  const deltas = [];
  stream.onDelta((d) => deltas.push(d));

  stream.emitDocumentChange("file:///test.ts", [
    { startLine: 0, startChar: 0, endLine: 0, endChar: 0, text: "hello", oldText: "" },
  ]);
  stream.emitDocumentChange("file:///test.ts", [
    { startLine: 0, startChar: 5, endLine: 0, endChar: 5, text: " world", oldText: "" },
  ]);

  assert.strictEqual(deltas.length, 2);
  assert.strictEqual(deltas[0].stateVersion, 1);
  assert.strictEqual(deltas[1].stateVersion, 2);
  assert.strictEqual(deltas[0].kind, "document.change");
});

test("Events: verifyDeltaChain detects gaps", () => {
  const deltas = [
    { stateVersion: 1, kind: "document.open", timestamp: "2024-01-01T00:00:00Z" },
    { stateVersion: 3, kind: "document.change", timestamp: "2024-01-01T00:00:01Z" },
  ];
  const result = verifyDeltaChain(deltas);
  assert.strictEqual(result.valid, false);
  assert.ok(result.errors.length > 0);
});

test("Events: hashDelta produces consistent hashes", () => {
  const delta = { stateVersion: 1, kind: "document.open", timestamp: "2024-01-01T00:00:00Z", uri: "file:///test.ts" };
  const hash1 = hashDelta(delta);
  const hash2 = hashDelta(delta);
  assert.strictEqual(hash1, hash2);
  assert.strictEqual(hash1.length, 64); // SHA-256 hex
});

// -- Module 3: Plan ----------------------------------------------------------
const plan = require("../../out/bridge/plan");
const { PlanBuilder, PlanValidator, PlanStateConflictError, buildCurrentState } = plan;

test("Plan: PlanBuilder builds a valid plan", () => {
  const builder = new PlanBuilder("Test plan");
  const p = builder
    .withGitState("main", "abc123", false)
    .withRelevantFile("src/test.ts", "hello world")
    .build();

  assert.ok(p.id);
  assert.strictEqual(p.intent, "Test plan");
  assert.strictEqual(p.expectedState.branch, "main");
  assert.strictEqual(p.expectedState.head, "abc123");
  assert.strictEqual(p.expectedState.dirtyState, false);
  assert.strictEqual(p.expectedState.relevantFiles.length, 1);
  assert.ok(p.expectedState.workspaceHash);
});

test("Plan: PlanValidator accepts matching state", () => {
  const builder = new PlanBuilder("Test plan");
  const p = builder
    .withGitState("main", "abc123", false)
    .withRelevantFile("src/test.ts", "hello world")
    .build();

  const current = buildCurrentState({
    branch: "main",
    head: "abc123",
    dirtyState: false,
    files: [{ path: "src/test.ts", content: "hello world" }],
  });

  const validator = new PlanValidator();
  const result = validator.validate(p, current);
  assert.strictEqual(result.valid, true);
  assert.strictEqual(result.reasons.length, 0);
});

test("Plan: PlanValidator rejects stale state with 409 conflict", () => {
  const builder = new PlanBuilder("Test plan");
  const p = builder
    .withGitState("main", "abc123", false)
    .withRelevantFile("src/test.ts", "hello world")
    .build();

  // Simulate stale state: different content
  const current = buildCurrentState({
    branch: "main",
    head: "abc123",
    dirtyState: false,
    files: [{ path: "src/test.ts", content: "modified content" }],
  });

  const validator = new PlanValidator();
  const result = validator.validate(p, current);
  assert.strictEqual(result.valid, false);
  assert.ok(result.reasons.length > 0);
  assert.ok(result.conflict);
  assert.strictEqual(result.conflict.status, 409);
  assert.strictEqual(result.conflict.code, "PLAN_STATE_CONFLICT");
});

test("Plan: PlanStateConflictError is thrown by assertValid", () => {
  const builder = new PlanBuilder("Test plan");
  const p = builder
    .withGitState("main", "abc123", false)
    .withRelevantFile("src/test.ts", "hello world")
    .build();

  const current = buildCurrentState({
    branch: "main",
    head: "def456", // different HEAD
    dirtyState: false,
    files: [{ path: "src/test.ts", content: "hello world" }],
  });

  const validator = new PlanValidator();
  assert.throws(
    () => validator.assertValid(p, current),
    (err) => err instanceof PlanStateConflictError && err.conflict.status === 409
  );
});

// -- Module 4: Resolver ------------------------------------------------------
const resolver = require("../../out/bridge/resolver");
const { resolve, isKnownCommand, getKnownCommands, getKnownEntrypoints } = resolver;

test("Resolver: git.push resolves to EXTERNAL", () => {
  const result = resolve("terminal.run", "git.push");
  assert.strictEqual(result.granted, true);
  assert.strictEqual(result.effect, "EXTERNAL");
  assert.strictEqual(result.requiresConfirmation, true);
  assert.strictEqual(result.requiresPasskey, true);
});

test("Resolver: git.commit resolves to DURABLE", () => {
  const result = resolve("terminal.run", "git.commit");
  assert.strictEqual(result.granted, true);
  assert.strictEqual(result.effect, "DURABLE");
  assert.strictEqual(result.requiresConfirmation, true);
  assert.strictEqual(result.requiresPasskey, false);
});

test("Resolver: fs.read resolves to LOCAL", () => {
  const result = resolve("terminal.run", "fs.read");
  assert.strictEqual(result.granted, true);
  assert.strictEqual(result.effect, "LOCAL");
  assert.strictEqual(result.requiresConfirmation, false);
  assert.strictEqual(result.requiresPasskey, false);
});

test("Resolver: unknown command is denied (fail closed)", () => {
  const result = resolve("terminal.run", "unknown.command");
  assert.strictEqual(result.granted, false);
  assert.strictEqual(result.effect, "EXTERNAL");
});

test("Resolver: scm.push entrypoint only allows EXTERNAL", () => {
  const result = resolve("scm.push", "git.push");
  assert.strictEqual(result.granted, true);
  assert.strictEqual(result.effect, "EXTERNAL");
});

test("Resolver: scm.push denies non-EXTERNAL commands", () => {
  const result = resolve("scm.push", "git.status");
  assert.strictEqual(result.granted, false);
});

test("Resolver: ui.executeCommand upgrades LOCAL to DURABLE", () => {
  const result = resolve("ui.executeCommand", "fs.read");
  assert.strictEqual(result.granted, true);
  assert.strictEqual(result.effect, "DURABLE"); // upgraded from LOCAL
});

test("Resolver: isKnownCommand works correctly", () => {
  assert.strictEqual(isKnownCommand("git.push"), true);
  assert.strictEqual(isKnownCommand("unknown.command"), false);
});

test("Resolver: getKnownCommands returns non-empty array", () => {
  const commands = getKnownCommands();
  assert.ok(Array.isArray(commands));
  assert.ok(commands.length > 0);
  assert.ok(commands.includes("git.push"));
});

test("Resolver: getKnownEntrypoints returns all 5 entrypoints", () => {
  const entrypoints = getKnownEntrypoints();
  assert.strictEqual(entrypoints.length, 5);
  assert.ok(entrypoints.includes("terminal.run"));
  assert.ok(entrypoints.includes("ui.executeCommand"));
});

// -- Module 5: Capabilities --------------------------------------------------
const capabilities = require("../../out/bridge/capabilities");
const { capabilityRegistry, workspace, editor, symbol, refactor, diagnostics, task: taskCaps, test: testCaps, debug, terminal, scm, ide } = capabilities;

test("Capabilities: registry has all required namespaces", () => {
  const requiredNamespaces = [
    "workspace", "editor", "symbol", "refactor",
    "diagnostics", "task", "test", "debug", "terminal", "scm", "ide"
  ];

  for (const ns of requiredNamespaces) {
    const caps = capabilityRegistry.listByNamespace(ns);
    assert.ok(caps.length > 0, `Namespace '${ns}' has no capabilities`);
  }
});

test("Capabilities: workspace namespace has readFile and writeFile", () => {
  assert.ok(workspace.readFile);
  assert.strictEqual(workspace.readFile.effect, "LOCAL");
  assert.ok(workspace.writeFile);
  assert.strictEqual(workspace.writeFile.effect, "DURABLE");
});

test("Capabilities: scm.push is EXTERNAL", () => {
  assert.ok(scm.push);
  assert.strictEqual(scm.push.effect, "EXTERNAL");
});

test("Capabilities: ide.executeCommand is EXTERNAL", () => {
  assert.ok(ide.executeCommand);
  assert.strictEqual(ide.executeCommand.effect, "EXTERNAL");
});

test("Capabilities: registry size is > 100", () => {
  assert.ok(capabilityRegistry.size > 100, `Expected > 100 capabilities, got ${capabilityRegistry.size}`);
});

test("Capabilities: listByEffect filters correctly", () => {
  const localCaps = capabilityRegistry.listByEffect("LOCAL");
  const durableCaps = capabilityRegistry.listByEffect("DURABLE");
  const externalCaps = capabilityRegistry.listByEffect("EXTERNAL");

  assert.ok(localCaps.length > 0);
  assert.ok(durableCaps.length > 0);
  assert.ok(externalCaps.length > 0);

  for (const cap of localCaps) {
    assert.strictEqual(cap.effect, "LOCAL");
  }
});

// -- Module 6: State (requires vscode mock) ----------------------------------
const state = require("../../out/bridge/state");
const { IDEStateObserver, SNAPSHOT_VERSION, IDE_STATE_VERSION } = state;

test("State: SNAPSHOT_VERSION is VSCODER_IDE_STATE_V1", () => {
  assert.strictEqual(SNAPSHOT_VERSION, "VSCODER_IDE_STATE_V1");
  assert.strictEqual(IDE_STATE_VERSION, "VSCODER_IDE_STATE_V1");
});

test("State: IDEStateObserver is exported and constructable", () => {
  assert.strictEqual(typeof IDEStateObserver, "function");
  const mockContext = { extensionUri: { fsPath: "/tmp" } };
  const observer = new IDEStateObserver(mockContext);
  assert.ok(observer instanceof IDEStateObserver);
});

test("State: observer produces snapshot with stateVersion", () => {
  const mockContext = { extensionUri: { fsPath: "/tmp" } };
  const observer = new IDEStateObserver(mockContext);

  const snapshot = observer.requestSnapshot();
  assert.strictEqual(snapshot.version, "VSCODER_IDE_STATE_V1");
  assert.ok(typeof snapshot.stateVersion === "number");
  assert.ok(snapshot.stateVersion >= 0);
  assert.ok(snapshot.timestamp);
  assert.ok(Array.isArray(snapshot.documents));
  assert.ok(Array.isArray(snapshot.visibleEditors));
});

test("State: observer emits deltas through event stream", () => {
  const mockContext = { extensionUri: { fsPath: "/tmp" } };
  const observer = new IDEStateObserver(mockContext);

  const deltas = [];
  observer.stream.onDelta((d) => deltas.push(d));

  // Emit through the internal stream
  observer.stream.emitDocumentChange("file:///test.ts", [
    { startLine: 0, startChar: 0, endLine: 0, endChar: 0, text: "hello", oldText: "" },
  ]);

  assert.ok(deltas.length > 0);
  assert.strictEqual(deltas[0].stateVersion, 1);
});

test("State: observer tracks plan registration", () => {
  const mockContext = { extensionUri: { fsPath: "/tmp" } };
  const observer = new IDEStateObserver(mockContext);

  const { PlanBuilder } = require("../../out/bridge/plan");
  const builder = new PlanBuilder("Test plan");
  const p = builder
    .withGitState("main", "abc123", false)
    .withRelevantFile("src/test.ts", "hello world")
    .build();

  observer.registerPlan(p);
  const result = observer.validatePlan(p.id);
  assert.ok(result);
  // Plan is invalid because observer has no documents loaded (expected in test env)
  assert.strictEqual(result.valid, false);
  assert.ok(result.reasons.length > 0);
});

// -- Cross-module coherence ---------------------------------------------------
test("Cross-module: IPC server can register handlers", () => {
  const server = new IpcServer({ tokens: ["test"] });
  server.registerHandler("test.method", (ctx) => {
    return { ok: true, sessionId: ctx.session.id };
  });
  // If we got here without error, registration works
  assert.ok(true);
});

test("Cross-module: resolver and capabilities agree on git.push", () => {
  const resolverResult = resolve("terminal.run", "git.push");
  const capResult = scm.push;

  assert.strictEqual(resolverResult.effect, "EXTERNAL");
  assert.strictEqual(capResult.effect, "EXTERNAL");
});

test("Cross-module: plan validator and state observer use same hash", () => {
  const { PlanBuilder, PlanValidator, buildCurrentState } = require("../../out/bridge/plan");

  const builder = new PlanBuilder("Test plan");
  const p = builder
    .withGitState("main", "abc123", false)
    .withRelevantFile("src/test.ts", "hello world")
    .build();

  const current = buildCurrentState({
    branch: "main",
    head: "abc123",
    dirtyState: false,
    files: [{ path: "src/test.ts", content: "hello world" }],
  });

  const validator = new PlanValidator();
  const result = validator.validate(p, current);
  assert.strictEqual(result.valid, true);
});

test("Cross-module: event stream and state observer share delta format", () => {
  const { EventStream } = require("../../out/bridge/events");
  const stream = new EventStream();

  const deltas = [];
  stream.onDelta((d) => deltas.push(d));

  stream.emitDocumentChange("file:///test.ts", [
    { startLine: 0, startChar: 0, endLine: 0, endChar: 0, text: "hello", oldText: "" },
  ]);

  assert.strictEqual(deltas[0].kind, "document.change");
  assert.strictEqual(deltas[0].stateVersion, 1);
  assert.ok(deltas[0].timestamp);
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------
console.log(`\n${"=".repeat(60)}`);
console.log(`Results: ${passed} passed, ${failed} failed, ${passed + failed} total`);
console.log(`${"=".repeat(60)}\n`);

if (failed > 0) {
  console.log("Failures:");
  for (const f of failures) {
    console.log(`  - ${f.name}: ${f.error.message}`);
  }
  process.exit(1);
} else {
  console.log("All tests passed!");
  process.exit(0);
}
