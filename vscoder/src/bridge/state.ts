/**
 * VSCODER:// IDE State Observer — bridge/state.ts
 *
 * Phase 2: Native VS Code event subscriber that maintains a versioned snapshot
 * (VSCODER_IDE_STATE_V1) with monotonically increasing stateVersion, emits
 * compact deltas on every change, supports full snapshot on request, excludes
 * secrets from state/events/logs, and handles human edits (invalidates affected
 * plans).
 *
 * Design principles:
 *   - Thin observer: subscribes to native VS Code events, maintains state,
 *     emits deltas. No routing intelligence here — that lives in Python.
 *   - Compact deltas: only changed fields are emitted.
 *   - Full snapshot: available on demand via requestSnapshot().
 *   - Secret exclusion: all state/events pass through sanitize().
 *   - Human-edit invalidation: when a human edits a file, affected plans are
 *     invalidated via the plan invalidation callback.
 *   - Monotonic stateVersion: every event increments stateVersion by exactly 1.
 *
 * Self-contained: imports only from vscode, events.ts, and plan.ts.
 */

import * as vscode from "vscode";
import {
  EventStream,
  DeltaEvent,
  SnapshotEvent,
  DeltaKind,
  TextChange,
  SelectionInfo,
  DiagnosticSummary,
  sanitize,
} from "./events";
import { Plan, ExpectedState, CurrentState, ValidationResult } from "./plan";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Snapshot format version identifier. */
export const SNAPSHOT_VERSION = "VSCODER_IDE_STATE_V1" as const;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A plan invalidation event triggered by a human edit. */
export interface PlanInvalidation {
  /** The URI that was human-edited. */
  uri: string;
  /** The stateVersion at which the edit was detected. */
  stateVersion: number;
  /** Plans that were invalidated by this edit. */
  invalidatedPlans: string[];
  /** ISO-8601 timestamp. */
  timestamp: string;
}

/** Configuration change delta. */
export interface ConfigChange {
  /** The configuration section that changed, e.g. "vscoder.webmcpPort". */
  section: string;
  /** The old value (sanitized). */
  oldValue: unknown;
  /** The new value (sanitized). */
  newValue: unknown;
}

/** SCM (source control) state. */
export interface SCMState {
  /** SCM provider ID, e.g. "git". */
  id: string;
  /** Label, e.g. "Git". */
  label: string;
  /** Number of changed resources. */
  changeCount: number;
}

/** Debug session state. */
export interface DebugState {
  /** Whether a debug session is active. */
  active: boolean;
  /** Session ID (if active). */
  sessionId?: string;
  /** Session type (if active). */
  sessionType?: string;
  /** Session name (if active). */
  sessionName?: string;
  /** Number of breakpoints. */
  breakpointCount: number;
}

/** Task state. */
export interface TaskState {
  /** Whether a task is currently running. */
  running: boolean;
  /** Task name (if running). */
  name?: string;
  /** Task source (if running). */
  source?: string;
}

/** Test run state. */
export interface TestState {
  /** Whether tests are running. */
  running: boolean;
  /** Test run ID (if running). */
  runId?: string;
  /** Number of passed tests (last run). */
  passed: number;
  /** Number of failed tests (last run). */
  failed: number;
  /** Number of skipped tests (last run). */
  skipped: number;
}

/** The complete IDE state snapshot. */
export interface IDEStateSnapshot {
  /** Snapshot format version. */
  version: typeof SNAPSHOT_VERSION;
  /** Monotonically increasing state version. */
  stateVersion: number;
  /** ISO-8601 timestamp. */
  timestamp: string;
  /** All open documents. */
  documents: DocumentSnapshot[];
  /** All visible editors. */
  visibleEditors: EditorSnapshot[];
  /** Workspace folders. */
  workspaceFolders: string[];
  /** Active editor URI. */
  activeEditor?: string;
  /** Extension state. */
  extension: {
    version: string;
    state: "activating" | "active" | "deactivating" | "inactive";
  };
  /** SCM providers. */
  scm: SCMState[];
  /** Debug state. */
  debug: DebugState;
  /** Task state. */
  task: TaskState;
  /** Test state. */
  test: TestState;
  /** Configuration (sanitized). */
  configuration: Record<string, unknown>;
}

/** A single document's full state. */
export interface DocumentSnapshot {
  uri: string;
  language: string;
  version: number;
  lineCount: number;
  content: string;
  isDirty: boolean;
}

/** A single editor's full state. */
export interface EditorSnapshot {
  uri: string;
  selection: SelectionInfo;
  visibleRanges: Array<{ start: number; end: number }>;
}

/** A compact delta event with extended kinds for full IDE coverage. */
export interface IDEDeltaEvent extends DeltaEvent {
  kind: ExtendedDeltaKind;
}

/** Extended delta kinds covering all VS Code event types. */
export type ExtendedDeltaKind =
  | DeltaKind
  | "config.change"
  | "scm.change"
  | "debug.start"
  | "debug.stop"
  | "debug.breakpoint"
  | "task.start"
  | "task.end"
  | "test.start"
  | "test.end"
  | "human.edit";

/** Callback for plan invalidation events. */
export type PlanInvalidationHandler = (invalidation: PlanInvalidation) => void;

/** Callback for delta events. */
export type DeltaHandler = (event: IDEDeltaEvent) => void;

/** Callback for snapshot events. */
export type SnapshotHandler = (snapshot: IDEStateSnapshot) => void;

// ---------------------------------------------------------------------------
// IDE State Observer
// ---------------------------------------------------------------------------

/**
 * The main IDE State Observer class.
 *
 * Subscribes to native VS Code events, maintains a versioned snapshot,
 * emits compact deltas, and handles human-edit plan invalidation.
 *
 * Usage:
 *   const observer = new IDEStateObserver();
 *   observer.onDelta((event) => { ... });
 *   observer.onSnapshot((snapshot) => { ... });
 *   observer.onPlanInvalidation((inv) => { ... });
 *   observer.activate();  // Start listening
 *   observer.deactivate(); // Stop listening
 */
export class IDEStateObserver {
  private eventStream: EventStream;
  private context: vscode.ExtensionContext;
  private disposables: vscode.Disposable[] = [];
  private deltaHandlers: DeltaHandler[] = [];
  private snapshotHandlers: SnapshotHandler[] = [];
  private planInvalidationHandlers: PlanInvalidationHandler[] = [];
  private active: boolean = false;

  // Internal state
  private documents: Map<string, DocumentSnapshot> = new Map();
  private visibleEditors: Map<string, EditorSnapshot> = new Map();
  private workspaceFolders: string[] = [];
  private activeEditor: string | undefined;
  private extensionState: "activating" | "active" | "deactivating" | "inactive" = "inactive";
  private scmProviders: SCMState[] = [];
  private debugState: DebugState = { active: false, breakpointCount: 0 };
  private taskState: TaskState = { running: false };
  private testState: TestState = { running: false, passed: 0, failed: 0, skipped: 0 };
  private configuration: Record<string, unknown> = {};

  // Plan tracking
  private activePlans: Map<string, Plan> = new Map();
  private planFileIndex: Map<string, Set<string>> = new Map(); // file URI -> plan IDs

  // Human edit detection
  private lastKnownVersions: Map<string, number> = new Map();
  private humanEditGraceMs: number = 500; // Grace period to avoid false positives

  constructor(
    context: vscode.ExtensionContext,
    options: { maxHistorySize?: number; extensionVersion?: string } = {},
  ) {
    this.context = context;
    this.eventStream = new EventStream(options);
    this.extensionState = "activating";
  }

  // -------------------------------------------------------------------------
  // Activation / Deactivation
  // -------------------------------------------------------------------------

  /**
   * Activate the observer: subscribe to all native VS Code events.
   */
  activate(): void {
    if (this.active) return;
    this.active = true;
    this.extensionState = "active";

    // Document events
    this.disposables.push(
      vscode.workspace.onDidOpenTextDocument(this.onDidOpenDocument, this),
      vscode.workspace.onDidCloseTextDocument(this.onDidCloseDocument, this),
      vscode.workspace.onDidChangeTextDocument(this.onDidChangeDocument, this),
      vscode.workspace.onDidSaveTextDocument(this.onDidSaveDocument, this),
      vscode.workspace.onDidCreateFiles(this.onDidCreateFiles, this),
      vscode.workspace.onDidDeleteFiles(this.onDidDeleteFiles, this),
      vscode.workspace.onDidRenameFiles(this.onDidRenameFiles, this),
      vscode.workspace.onDidChangeWorkspaceFolders(this.onDidChangeWorkspaceFolders, this),
      vscode.workspace.onDidChangeConfiguration(this.onDidChangeConfiguration, this),
    );

    // Editor events
    this.disposables.push(
      vscode.window.onDidChangeActiveTextEditor(this.onDidChangeActiveEditor, this),
      vscode.window.onDidChangeTextEditorSelection(this.onDidChangeSelection, this),
      vscode.window.onDidChangeVisibleTextEditors(this.onDidChangeVisibleEditors, this),
      vscode.window.onDidChangeTextEditorVisibleRanges(this.onDidChangeVisibleRanges, this),
    );

    // Diagnostics
    this.disposables.push(
      vscode.languages.onDidChangeDiagnostics(this.onDidChangeDiagnostics, this),
    );

    // SCM events
    this.disposables.push(
      vscode.workspace.onDidOpenTextDocument(this.refreshSCM, this),
      vscode.workspace.onDidSaveTextDocument(this.refreshSCM, this),
    );

    // Debug events
    this.disposables.push(
      vscode.debug.onDidStartDebugSession(this.onDidStartDebugSession, this),
      vscode.debug.onDidTerminateDebugSession(this.onDidTerminateDebugSession, this),
      vscode.debug.onDidChangeBreakpoints(this.onDidChangeBreakpoints, this),
    );

    // Task events
    this.disposables.push(
      vscode.tasks.onDidStartTask(this.onDidStartTask, this),
      vscode.tasks.onDidEndTask(this.onDidEndTask, this),
    );

    // Test events (via test controller)
    this.disposables.push(
      (vscode as { tests?: { onDidChangeTestResults?: vscode.Event<{ passed?: number; failed?: number; total?: number }> } }).tests?.onDidChangeTestResults?.(this.onDidChangeTestResults, this) ?? { dispose: () => {} },
    );

    // Extension state
    this.disposables.push(
      (vscode as unknown as { extensions?: { onDidChange?: vscode.Event<{ added: readonly vscode.Extension<unknown>[]; removed: readonly vscode.Extension<unknown>[] }> } }).extensions?.onDidChange?.(this.onDidChangeExtensions, this) ?? { dispose: () => {} },
    );

    // Initial state capture
    this.captureInitialState();

    // Emit activation delta
    this.emitDelta("extension.activate", {
      meta: { state: "active" },
    });
  }

  /**
   * Deactivate the observer: dispose all subscriptions.
   */
  deactivate(): void {
    if (!this.active) return;
    this.active = false;
    this.extensionState = "deactivating";

    for (const d of this.disposables) {
      d.dispose();
    }
    this.disposables = [];

    this.extensionState = "inactive";
    this.emitDelta("extension.deactivate", {
      meta: { state: "inactive" },
    });
  }

  // -------------------------------------------------------------------------
  // Handler Registration
  // -------------------------------------------------------------------------

  /** Register a handler for delta events. */
  onDelta(handler: DeltaHandler): () => void {
    this.deltaHandlers.push(handler);
    return () => {
      const idx = this.deltaHandlers.indexOf(handler);
      if (idx >= 0) this.deltaHandlers.splice(idx, 1);
    };
  }

  /** Register a handler for snapshot events. */
  onSnapshot(handler: SnapshotHandler): () => void {
    this.snapshotHandlers.push(handler);
    return () => {
      const idx = this.snapshotHandlers.indexOf(handler);
      if (idx >= 0) this.snapshotHandlers.splice(idx, 1);
    };
  }

  /** Register a handler for plan invalidation events. */
  onPlanInvalidation(handler: PlanInvalidationHandler): () => void {
    this.planInvalidationHandlers.push(handler);
    return () => {
      const idx = this.planInvalidationHandlers.indexOf(handler);
      if (idx >= 0) this.planInvalidationHandlers.splice(idx, 1);
    };
  }

  // -------------------------------------------------------------------------
  // Plan Management
  // -------------------------------------------------------------------------

  /**
   * Register a plan for tracking. The plan will be invalidated if any of its
   * relevant files are human-edited.
   */
  registerPlan(plan: Plan): void {
    this.activePlans.set(plan.id, plan);

    // Index the plan's relevant files
    for (const file of plan.expectedState.relevantFiles) {
      const uri = this.filePathToUri(file.path);
      if (!this.planFileIndex.has(uri)) {
        this.planFileIndex.set(uri, new Set());
      }
      this.planFileIndex.get(uri)!.add(plan.id);
    }
  }

  /**
   * Unregister a plan (e.g., after it has been executed or cancelled).
   */
  unregisterPlan(planId: string): void {
    const plan = this.activePlans.get(planId);
    if (!plan) return;

    // Remove from file index
    for (const file of plan.expectedState.relevantFiles) {
      const uri = this.filePathToUri(file.path);
      const plans = this.planFileIndex.get(uri);
      if (plans) {
        plans.delete(planId);
        if (plans.size === 0) {
          this.planFileIndex.delete(uri);
        }
      }
    }

    this.activePlans.delete(planId);
  }

  /**
   * Validate a plan against the current IDE state.
   */
  validatePlan(planId: string): ValidationResult | undefined {
    const plan = this.activePlans.get(planId);
    if (!plan) return undefined;

    const currentState = this.captureCurrentState();
    return this.compareStates(plan.expectedState, currentState);
  }

  // -------------------------------------------------------------------------
  // Snapshot
  // -------------------------------------------------------------------------

  /**
   * Request a full snapshot of the current IDE state.
   */
  requestSnapshot(): IDEStateSnapshot {
    const snapshot: IDEStateSnapshot = {
      version: SNAPSHOT_VERSION,
      stateVersion: this.eventStream.currentStateVersion,
      timestamp: new Date().toISOString(),
      documents: Array.from(this.documents.values()),
      visibleEditors: Array.from(this.visibleEditors.values()),
      workspaceFolders: [...this.workspaceFolders],
      activeEditor: this.activeEditor,
      extension: {
        version: "0.1.0",
        state: this.extensionState,
      },
      scm: [...this.scmProviders],
      debug: { ...this.debugState },
      task: { ...this.taskState },
      test: { ...this.testState },
      configuration: sanitize({ ...this.configuration }),
    };

    // Notify snapshot handlers
    for (const handler of this.snapshotHandlers) {
      try {
        handler(snapshot);
      } catch (err) {
        console.error("VSCODER: snapshot handler error:", err);
      }
    }

    return snapshot;
  }

  /**
   * Get the current state version.
   */
  get currentStateVersion(): number {
    return this.eventStream.currentStateVersion;
  }

  /**
   * Get the underlying EventStream (for advanced use).
   */
  get stream(): EventStream {
    return this.eventStream;
  }

  // -------------------------------------------------------------------------
  // Document Event Handlers
  // -------------------------------------------------------------------------

  private onDidOpenDocument(doc: vscode.TextDocument): void {
    const snapshot: DocumentSnapshot = {
      uri: doc.uri.toString(),
      language: doc.languageId,
      version: doc.version,
      lineCount: doc.lineCount,
      content: doc.getText(),
      isDirty: doc.isDirty,
    };
    this.documents.set(doc.uri.toString(), snapshot);
    this.lastKnownVersions.set(doc.uri.toString(), doc.version);

    this.emitDelta("document.open", {
      uri: doc.uri.toString(),
      language: doc.languageId,
      meta: { lineCount: doc.lineCount },
    });
  }

  private onDidCloseDocument(doc: vscode.TextDocument): void {
    const uri = doc.uri.toString();
    this.documents.delete(uri);
    this.lastKnownVersions.delete(uri);

    if (this.activeEditor === uri) {
      this.activeEditor = undefined;
    }

    this.emitDelta("document.close", { uri });
  }

  private onDidChangeDocument(event: vscode.TextDocumentChangeEvent): void {
    const uri = event.document.uri.toString();
    const doc = event.document;

    // Update document state
    const existing = this.documents.get(uri);
    const newSnapshot: DocumentSnapshot = {
      uri,
      language: doc.languageId,
      version: doc.version,
      lineCount: doc.lineCount,
      content: doc.getText(),
      isDirty: doc.isDirty,
    };
    this.documents.set(uri, newSnapshot);

    // Build text changes
    const changes: TextChange[] = event.contentChanges.map((change) => ({
      startLine: change.range.start.line,
      startChar: change.range.start.character,
      endLine: change.range.end.line,
      endChar: change.range.end.character,
      text: change.text,
      oldText: existing?.content
        ? this.extractOldText(existing.content, change.range)
        : "",
    }));

    // Check for human edit
    const lastVersion = this.lastKnownVersions.get(uri);
    const isHumanEdit = lastVersion !== undefined && doc.version > lastVersion + 1;

    this.lastKnownVersions.set(uri, doc.version);

    this.emitDelta("document.change", {
      uri,
      language: doc.languageId,
      changes,
    });

    // Handle human edit: invalidate affected plans
    if (isHumanEdit) {
      this.handleHumanEdit(uri);
    }
  }

  private onDidSaveDocument(doc: vscode.TextDocument): void {
    const uri = doc.uri.toString();
    const existing = this.documents.get(uri);
    if (existing) {
      existing.isDirty = false;
      existing.version = doc.version;
      existing.content = doc.getText();
      existing.lineCount = doc.lineCount;
    }

    this.emitDelta("document.save", { uri });
  }

  private onDidCreateFiles(event: vscode.FileCreateEvent): void {
    for (const uri of event.files) {
      this.emitDelta("workspace.change", {
        meta: { action: "create", uri: uri.toString() },
      });
    }
  }

  private onDidDeleteFiles(event: vscode.FileDeleteEvent): void {
    for (const uri of event.files) {
      const uriStr = uri.toString();
      this.documents.delete(uriStr);
      this.visibleEditors.delete(uriStr);
      this.lastKnownVersions.delete(uriStr);

      this.emitDelta("workspace.change", {
        meta: { action: "delete", uri: uriStr },
      });
    }
  }

  private onDidRenameFiles(event: vscode.FileRenameEvent): void {
    for (const { oldUri, newUri } of event.files) {
      const oldStr = oldUri.toString();
      const newStr = newUri.toString();

      // Update document state
      const doc = this.documents.get(oldStr);
      if (doc) {
        doc.uri = newStr;
        this.documents.set(newStr, doc);
        this.documents.delete(oldStr);
      }

      // Update editor state
      const editor = this.visibleEditors.get(oldStr);
      if (editor) {
        editor.uri = newStr;
        this.visibleEditors.set(newStr, editor);
        this.visibleEditors.delete(oldStr);
      }

      // Update last known versions
      const version = this.lastKnownVersions.get(oldStr);
      if (version !== undefined) {
        this.lastKnownVersions.set(newStr, version);
        this.lastKnownVersions.delete(oldStr);
      }

      this.emitDelta("workspace.change", {
        meta: { action: "rename", oldUri: oldStr, newUri: newStr },
      });
    }
  }

  // -------------------------------------------------------------------------
  // Editor Event Handlers
  // -------------------------------------------------------------------------

  private onDidChangeActiveEditor(editor: vscode.TextEditor | undefined): void {
    this.activeEditor = editor?.document.uri.toString();

    if (editor) {
      this.emitDelta("editor.visible", {
        visibleEditors: this.getVisibleEditorUris(),
      });
    }
  }

  private onDidChangeSelection(event: vscode.TextEditorSelectionChangeEvent): void {
    const editor = event.textEditor;
    const uri = editor.document.uri.toString();

    const selection: SelectionInfo = {
      active: {
        line: event.selections[0].active.line,
        character: event.selections[0].active.character,
      },
      start: {
        line: event.selections[0].start.line,
        character: event.selections[0].start.character,
      },
      end: {
        line: event.selections[0].end.line,
        character: event.selections[0].end.character,
      },
      isEmpty: event.selections[0].isEmpty,
    };

    // Update editor state
    const existing = this.visibleEditors.get(uri);
    if (existing) {
      existing.selection = selection;
    } else {
      this.visibleEditors.set(uri, {
        uri,
        selection,
        visibleRanges: [],
      });
    }

    this.emitDelta("editor.selection", { uri, selection });
  }

  private onDidChangeVisibleEditors(editors: readonly vscode.TextEditor[]): void {
    const uris = editors.map((e) => e.document.uri.toString());

    // Update visible editors map
    const newMap = new Map<string, EditorSnapshot>();
    for (const editor of editors) {
      const uri = editor.document.uri.toString();
      const existing = this.visibleEditors.get(uri);
      newMap.set(uri, {
        uri,
        selection: existing?.selection ?? {
          active: { line: 0, character: 0 },
          start: { line: 0, character: 0 },
          end: { line: 0, character: 0 },
          isEmpty: true,
        },
        visibleRanges: existing?.visibleRanges ?? [],
      });
    }
    this.visibleEditors = newMap;

    this.emitDelta("editor.visible", { visibleEditors: uris });
  }

  private onDidChangeVisibleRanges(event: vscode.TextEditorVisibleRangesChangeEvent): void {
    const uri = event.textEditor.document.uri.toString();
    const existing = this.visibleEditors.get(uri);
    if (existing) {
      existing.visibleRanges = event.visibleRanges.map((r) => ({
        start: r.start.line,
        end: r.end.line,
      }));
    }
  }

  // -------------------------------------------------------------------------
  // Workspace Event Handlers
  // -------------------------------------------------------------------------

  private onDidChangeWorkspaceFolders(event: vscode.WorkspaceFoldersChangeEvent): void {
    this.workspaceFolders = vscode.workspace.workspaceFolders?.map((f) => f.uri.toString()) ?? [];

    this.emitDelta("workspace.change", {
      meta: {
        added: event.added.map((f) => f.uri.toString()),
        removed: event.removed.map((f) => f.uri.toString()),
      },
    });
  }

  private onDidChangeConfiguration(event: vscode.ConfigurationChangeEvent): void {
    const changes: ConfigChange[] = [];

    // Check all vscoder.* settings
    const config = vscode.workspace.getConfiguration("vscoder");
    for (const key of ["webmcpPort", "ollamaUrl", "pythonPath"]) {
      const section = `vscoder.${key}`;
      if (event.affectsConfiguration(section)) {
        const newValue = sanitize(config.get(key));
        changes.push({
          section,
          oldValue: this.configuration[section] ?? null,
          newValue,
        });
        this.configuration[section] = newValue;
      }
    }

    for (const change of changes) {
      this.emitDelta("config.change", {
        meta: { configChange: change },
      });
    }
  }

  // -------------------------------------------------------------------------
  // Diagnostics Event Handlers
  // -------------------------------------------------------------------------

  private onDidChangeDiagnostics(event: vscode.DiagnosticChangeEvent): void {
    for (const uri of event.uris) {
      const diagnostics = vscode.languages.getDiagnostics(uri);
      const summary: DiagnosticSummary = {
        errors: 0,
        warnings: 0,
        infos: 0,
        hints: 0,
      };

      for (const d of diagnostics) {
        switch (d.severity) {
          case vscode.DiagnosticSeverity.Error:
            summary.errors++;
            break;
          case vscode.DiagnosticSeverity.Warning:
            summary.warnings++;
            break;
          case vscode.DiagnosticSeverity.Information:
            summary.infos++;
            break;
          case vscode.DiagnosticSeverity.Hint:
            summary.hints++;
            break;
        }
      }

      this.emitDelta("diagnostic", {
        uri: uri.toString(),
        diagnostics: summary,
      });
    }
  }

  // -------------------------------------------------------------------------
  // SCM Event Handlers
  // -------------------------------------------------------------------------

  private refreshSCM(): void {
    // VS Code doesn't have a direct SCM change event that works reliably
    // across all providers. We refresh SCM state on document events.
    const scmProviders: SCMState[] = [];

    // Try to get git extension
    const gitExt = vscode.extensions.getExtension("vscode.git");
    if (gitExt?.isActive) {
      const git = gitExt.exports;
      const api = git.getAPI(1);
      if (api?.repositories) {
        for (const repo of api.repositories) {
          const changes = repo.state?.changes ?? [];
          scmProviders.push({
            id: "git",
            label: "Git",
            changeCount: changes.length,
          });
        }
      }
    }

    this.scmProviders = scmProviders;
    this.emitDelta("scm.change", {
      meta: { providers: scmProviders },
    });
  }

  // -------------------------------------------------------------------------
  // Debug Event Handlers
  // -------------------------------------------------------------------------

  private onDidStartDebugSession(session: vscode.DebugSession): void {
    this.debugState = {
      active: true,
      sessionId: session.id,
      sessionType: session.type,
      sessionName: session.name,
      breakpointCount: this.debugState.breakpointCount,
    };

    this.emitDelta("debug.start", {
      meta: {
        sessionId: session.id,
        sessionType: session.type,
        sessionName: session.name,
      },
    });
  }

  private onDidTerminateDebugSession(session: vscode.DebugSession): void {
    this.debugState = {
      active: false,
      breakpointCount: this.debugState.breakpointCount,
    };

    this.emitDelta("debug.stop", {
      meta: { sessionId: session.id },
    });
  }

  private onDidChangeBreakpoints(event: vscode.BreakpointsChangeEvent): void {
    const allBreakpoints = vscode.debug.breakpoints;
    this.debugState.breakpointCount = allBreakpoints.length;

    this.emitDelta("debug.breakpoint", {
      meta: {
        added: event.added.length,
        removed: event.removed.length,
        changed: event.changed.length,
        total: allBreakpoints.length,
      },
    });
  }

  // -------------------------------------------------------------------------
  // Task Event Handlers
  // -------------------------------------------------------------------------

  private onDidStartTask(event: vscode.TaskStartEvent): void {
    const task = event.execution.task;
    this.taskState = {
      running: true,
      name: task.name,
      source: task.source,
    };

    this.emitDelta("task.start", {
      meta: {
        taskName: task.name,
        taskSource: task.source,
      },
    });
  }

  private onDidEndTask(event: vscode.TaskEndEvent): void {
    this.taskState = { running: false };

    this.emitDelta("task.end", {
      meta: {
        taskName: event.execution.task.name,
      },
    });
  }

  // -------------------------------------------------------------------------
  // Test Event Handlers
  // -------------------------------------------------------------------------

  private onDidChangeTestResults(event: { passed?: number; failed?: number; total?: number }): void {
    // VS Code test results API varies by version
    // This is a best-effort implementation
    const e = event as { passed?: number; failed?: number; skipped?: number };
    this.testState = {
      running: false,
      passed: e.passed ?? 0,
      failed: e.failed ?? 0,
      skipped: e.skipped ?? 0,
    };

    this.emitDelta("test.end", {
      meta: {
        passed: e.passed ?? 0,
        failed: e.failed ?? 0,
        skipped: e.skipped ?? 0,
      },
    });
  }

  // -------------------------------------------------------------------------
  // Extension Event Handlers
  // -------------------------------------------------------------------------

  private onDidChangeExtensions(event: { added: readonly vscode.Extension<unknown>[]; removed: readonly vscode.Extension<unknown>[] }): void {
    // Re-emit extension state if our extension was affected
    const ourExt = event.added.find((e: vscode.Extension<unknown>) => e.id === "vscoder.vscoder");
    if (ourExt) {
      this.extensionState = "active";
    }
  }

  // -------------------------------------------------------------------------
  // Human Edit Detection & Plan Invalidation
  // -------------------------------------------------------------------------

  /**
   * Handle a human edit: invalidate all plans that depend on the edited file.
   */
  private handleHumanEdit(uri: string): void {
    const planIds = this.planFileIndex.get(uri);
    if (!planIds || planIds.size === 0) return;

    const invalidatedPlans: string[] = [];
    for (const planId of planIds) {
      const plan = this.activePlans.get(planId);
      if (plan) {
        // Validate the plan against current state
        const currentState = this.captureCurrentState();
        const result = this.compareStates(plan.expectedState, currentState);

        if (!result.valid) {
          invalidatedPlans.push(planId);
          // Optionally unregister the plan
          // this.unregisterPlan(planId);
        }
      }
    }

    if (invalidatedPlans.length > 0) {
      const invalidation: PlanInvalidation = {
        uri,
        stateVersion: this.eventStream.currentStateVersion,
        invalidatedPlans,
        timestamp: new Date().toISOString(),
      };

      // Emit human.edit delta
      this.emitDelta("human.edit", {
        uri,
        meta: { invalidatedPlans },
      });

      // Notify plan invalidation handlers
      for (const handler of this.planInvalidationHandlers) {
        try {
          handler(invalidation);
        } catch (err) {
          console.error("VSCODER: plan invalidation handler error:", err);
        }
      }
    }
  }

  // -------------------------------------------------------------------------
  // State Capture & Comparison
  // -------------------------------------------------------------------------

  /**
   * Capture the current state for plan validation.
   */
  private captureCurrentState(): CurrentState {
    const relevantFiles: Array<{ path: string; hash: string }> = [];

    for (const [uri, doc] of this.documents) {
      const path = this.uriToFilePath(uri);
      if (path) {
        relevantFiles.push({
          path,
          hash: this.hashContent(doc.content),
        });
      }
    }

    // Get git state
    let branch = "unknown";
    let head = "unknown";
    let dirtyState = false;

    const gitExt = vscode.extensions.getExtension("vscode.git");
    if (gitExt?.isActive) {
      const git = gitExt.exports;
      const api = git.getAPI(1);
      if (api?.repositories?.[0]) {
        const repo = api.repositories[0];
        branch = repo.state?.HEAD?.name ?? "unknown";
        head = repo.state?.HEAD?.commit ?? "unknown";
        dirtyState = (repo.state?.changes?.length ?? 0) > 0;
      }
    }

    // Compute workspace hash
    const workspaceHash = this.hashContent(
      relevantFiles.map((f) => `${f.path}:${f.hash}`).join("\n"),
    );

    return {
      workspaceHash,
      branch,
      head,
      dirtyState,
      relevantFiles,
    };
  }

  /**
   * Compare expected state against current state.
   */
  private compareStates(expected: ExpectedState, current: CurrentState): ValidationResult {
    const reasons: string[] = [];

    if (expected.workspaceHash !== current.workspaceHash) {
      // Check which files differ
      const expectedFiles = new Map(expected.relevantFiles.map((f) => [f.path, f.hash]));
      const currentFiles = new Map(current.relevantFiles.map((f) => [f.path, f.hash]));

      for (const [path, hash] of expectedFiles) {
        const currentHash = currentFiles.get(path);
        if (currentHash !== hash) {
          reasons.push(`File changed: ${path}`);
        }
      }

      for (const path of currentFiles.keys()) {
        if (!expectedFiles.has(path)) {
          reasons.push(`New file: ${path}`);
        }
      }
    }

    if (expected.branch !== current.branch) {
      reasons.push(`Branch changed: ${expected.branch} → ${current.branch}`);
    }

    if (expected.head !== current.head) {
      reasons.push(`HEAD changed: ${expected.head} → ${current.head}`);
    }

    if (expected.dirtyState !== current.dirtyState) {
      reasons.push(`Dirty state changed: ${expected.dirtyState} → ${current.dirtyState}`);
    }

    return {
      valid: reasons.length === 0,
      reasons,
    };
  }

  // -------------------------------------------------------------------------
  // Initial State Capture
  // -------------------------------------------------------------------------

  /**
   * Capture the initial state when the observer is activated.
   */
  private captureInitialState(): void {
    // Capture workspace folders
    this.workspaceFolders = vscode.workspace.workspaceFolders?.map((f) => f.uri.toString()) ?? [];

    // Capture open documents
    for (const doc of vscode.workspace.textDocuments) {
      const snapshot: DocumentSnapshot = {
        uri: doc.uri.toString(),
        language: doc.languageId,
        version: doc.version,
        lineCount: doc.lineCount,
        content: doc.getText(),
        isDirty: doc.isDirty,
      };
      this.documents.set(doc.uri.toString(), snapshot);
      this.lastKnownVersions.set(doc.uri.toString(), doc.version);
    }

    // Capture visible editors
    for (const editor of vscode.window.visibleTextEditors) {
      const uri = editor.document.uri.toString();
      const selection: SelectionInfo = {
        active: {
          line: editor.selection.active.line,
          character: editor.selection.active.character,
        },
        start: {
          line: editor.selection.start.line,
          character: editor.selection.start.character,
        },
        end: {
          line: editor.selection.end.line,
          character: editor.selection.end.character,
        },
        isEmpty: editor.selection.isEmpty,
      };

      this.visibleEditors.set(uri, {
        uri,
        selection,
        visibleRanges: editor.visibleRanges.map((r) => ({
          start: r.start.line,
          end: r.end.line,
        })),
      });
    }

    // Capture active editor
    this.activeEditor = vscode.window.activeTextEditor?.document.uri.toString();

    // Capture configuration
    const config = vscode.workspace.getConfiguration("vscoder");
    this.configuration = {
      "vscoder.webmcpPort": config.get("webmcpPort"),
      "vscoder.ollamaUrl": config.get("ollamaUrl"),
      "vscoder.pythonPath": config.get("pythonPath"),
    };

    // Capture debug state
    this.debugState = {
      active: vscode.debug.activeDebugSession !== undefined,
      breakpointCount: vscode.debug.breakpoints.length,
    };

    // Refresh SCM
    this.refreshSCM();
  }

  // -------------------------------------------------------------------------
  // Delta Emission
  // -------------------------------------------------------------------------

  /**
   * Emit a delta event through the event stream and notify handlers.
   */
  private emitDelta(
    kind: ExtendedDeltaKind,
    partial: Omit<IDEDeltaEvent, "stateVersion" | "kind" | "timestamp">,
  ): void {
    // Use the event stream to get the next version and build the delta
    const version = this.eventStream.currentStateVersion + 1;

    // Build the delta event
    const event: IDEDeltaEvent = {
      stateVersion: version,
      kind,
      timestamp: new Date().toISOString(),
      ...partial,
    };

    // Sanitize the event
    const sanitized = sanitize(event);

    // Notify delta handlers
    for (const handler of this.deltaHandlers) {
      try {
        handler(sanitized);
      } catch (err) {
        console.error("VSCODER: delta handler error:", err);
      }
    }

    // Also emit through the event stream for history/resync
    // We use a trick: emit a minimal delta to the stream to advance the version
    this.eventStream.emitDocumentChange("__internal__", []);
  }

  // -------------------------------------------------------------------------
  // Utility Methods
  // -------------------------------------------------------------------------

  private getVisibleEditorUris(): string[] {
    return vscode.window.visibleTextEditors.map((e) => e.document.uri.toString());
  }

  private filePathToUri(filePath: string): string {
    return vscode.Uri.file(filePath).toString();
  }

  private uriToFilePath(uri: string): string | undefined {
    try {
      return vscode.Uri.parse(uri).fsPath;
    } catch {
      return undefined;
    }
  }

  private extractOldText(content: string, range: vscode.Range): string {
    const lines = content.split("\n");
    const result: string[] = [];

    for (let i = range.start.line; i <= range.end.line; i++) {
      if (i === range.start.line && i === range.end.line) {
        result.push(lines[i].substring(range.start.character, range.end.character));
      } else if (i === range.start.line) {
        result.push(lines[i].substring(range.start.character));
      } else if (i === range.end.line) {
        result.push(lines[i].substring(0, range.end.character));
      } else {
        result.push(lines[i]);
      }
    }

    return result.join("\n");
  }

  private hashContent(content: string): string {
    const crypto = require("crypto");
    return crypto.createHash("sha256").update(content, "utf8").digest("hex");
  }
}

// ---------------------------------------------------------------------------
// Re-exports
// ---------------------------------------------------------------------------

export { SNAPSHOT_VERSION as IDE_STATE_VERSION };
export type { IDEStateSnapshot as StateSnapshot };
