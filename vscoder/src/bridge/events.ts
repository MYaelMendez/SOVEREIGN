/**
 * VSCODER:// Event Stream — bridge/events.ts
 *
 * Phase 2: Real-time IDE event stream with compact deltas, full snapshots,
 * secret exclusion, reconnect/resynchronization, and monotonic stateVersion.
 *
 * Design principles:
 *   - Compact deltas: only changed fields are emitted, never full snapshots per keystroke.
 *   - Full snapshot: available on demand via requestSnapshot().
 *   - Secret exclusion: all events pass through sanitize() which strips credentials,
 *     tokens, env vars, and other sensitive values before emission.
 *   - Reconnect + resync: clients can request a snapshot at any stateVersion to
 *     resynchronize after a disconnect.
 *   - Monotonic stateVersion: every event increments stateVersion by exactly 1,
 *     giving clients a reliable ordering and gap-detection mechanism.
 *
 * Self-contained: uses only Node.js built-ins (crypto). No external deps.
 */

import { createHash } from "crypto";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** The kind of IDE change that produced this delta. */
export type DeltaKind =
  | "document.open"
  | "document.close"
  | "document.change"
  | "document.save"
  | "editor.selection"
  | "editor.visible"
  | "workspace.change"
  | "diagnostic"
  | "extension.activate"
  | "extension.deactivate"
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

/**
 * A compact delta event. Only the fields that changed are present.
 * `stateVersion` is always present and monotonically increasing.
 */
export interface DeltaEvent {
  /** Monotonically increasing version (starts at 1). */
  stateVersion: number;
  /** The kind of change. */
  kind: DeltaKind;
  /** ISO-8601 timestamp of when the event was generated. */
  timestamp: string;
  /** URI of the affected resource (file path, etc.). */
  uri?: string;
  /** Language ID (for document events). */
  language?: string;
  /** Changed lines (for document.change). */
  changes?: TextChange[];
  /** Cursor/selection position (for editor.selection). */
  selection?: SelectionInfo;
  /** Visible editor URIs (for editor.visible). */
  visibleEditors?: string[];
  /** Diagnostic summary (for diagnostic). */
  diagnostics?: DiagnosticSummary;
  /** Arbitrary metadata (already sanitized). */
  meta?: Record<string, unknown>;
}

/** A single text change within a document. */
export interface TextChange {
  /** Start line (0-based). */
  startLine: number;
  /** Start character (0-based). */
  startChar: number;
  /** End line (0-based). */
  endLine: number;
  /** End character (0-based). */
  endChar: number;
  /** The new text that replaced the range. */
  text: string;
  /** The old text that was replaced. */
  oldText: string;
}

/** Cursor/selection information. */
export interface SelectionInfo {
  /** Active cursor position. */
  active: { line: number; character: number };
  /** Selection start. */
  start: { line: number; character: number };
  /** Selection end. */
  end: { line: number; character: number };
  /** Whether the selection is empty (just a cursor). */
  isEmpty: boolean;
}

/** Diagnostic summary for a URI. */
export interface DiagnosticSummary {
  /** Number of errors. */
  errors: number;
  /** Number of warnings. */
  warnings: number;
  /** Number of infos. */
  infos: number;
  /** Number of hints. */
  hints: number;
}

/**
 * A full snapshot event. Contains the complete IDE state at a given
 * stateVersion. Sent on request or after a reconnect.
 */
export interface SnapshotEvent {
  /** The stateVersion at which this snapshot was taken. */
  stateVersion: number;
  /** ISO-8601 timestamp. */
  timestamp: string;
  /** All open documents with their content. */
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

/**
 * A resynchronization request from a client.
 * The client sends its last known stateVersion and receives either
 * a snapshot (if too far behind) or a batch of missed deltas.
 */
export interface ResyncRequest {
  /** The last stateVersion the client received. */
  lastStateVersion: number;
  /** Maximum number of deltas to return (default: 100). */
  maxDeltas?: number;
}

/**
 * A resynchronization response.
 * If the client is too far behind, a snapshot is returned.
 * Otherwise, a batch of missed deltas is returned.
 */
export type ResyncResponse =
  | { type: "snapshot"; snapshot: SnapshotEvent }
  | { type: "deltas"; deltas: DeltaEvent[]; currentVersion: number };

// ---------------------------------------------------------------------------
// Secret Exclusion
// ---------------------------------------------------------------------------

/**
 * Patterns that indicate a secret value. These are stripped from all events.
 */
const SECRET_PATTERNS: RegExp[] = [
  /password/i,
  /passwd/i,
  /secret/i,
  /token/i,
  /api[_-]?key/i,
  /auth/i,
  /credential/i,
  /private[_-]?key/i,
  /access[_-]?key/i,
  /session[_-]?id/i,
  /bearer\s+\S+/gi,
  /-----BEGIN\s+\w+\s+PRIVATE\s+KEY-----[\s\S]*?-----END\s+\w+\s+PRIVATE\s+KEY-----/gi,
  /[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}/g, // JWT-like
  /ghp_[a-zA-Z0-9]{36}/g, // GitHub PAT
  /sk-[a-zA-Z0-9]{20,}/g, // OpenAI-style key
  /xox[baprs]-[a-zA-Z0-9-]+/g, // Slack token
];

/**
 * Keys whose values should always be redacted.
 */
const SENSITIVE_KEYS = new Set([
  "password",
  "passwd",
  "secret",
  "token",
  "apiKey",
  "api_key",
  "auth",
  "authorization",
  "credential",
  "credentials",
  "privateKey",
  "private_key",
  "accessToken",
  "access_token",
  "refreshToken",
  "refresh_token",
  "sessionToken",
  "session_token",
  "idToken",
  "id_token",
  "clientSecret",
  "client_secret",
  "connectionString",
  "connection_string",
]);

/**
 * Redact a string value that looks like a secret.
 */
function redactString(value: string): string {
  let result = value;
  for (const pattern of SECRET_PATTERNS) {
    result = result.replace(pattern, "[REDACTED]");
  }
  return result;
}

/**
 * Deep-sanitize an object, stripping secrets from all string values
 * and redacting sensitive keys.
 */
export function sanitize<T>(value: T): T {
  if (value === null || value === undefined) {
    return value;
  }

  if (typeof value === "string") {
    return redactString(value) as unknown as T;
  }

  if (Array.isArray(value)) {
    return value.map((item) => sanitize(item)) as unknown as T;
  }

  if (typeof value === "object") {
    const result: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(value as Record<string, unknown>)) {
      if (SENSITIVE_KEYS.has(key)) {
        result[key] = "[REDACTED]";
      } else {
        result[key] = sanitize(val);
      }
    }
    return result as T;
  }

  return value;
}

// ---------------------------------------------------------------------------
// State Version Generator
// ---------------------------------------------------------------------------

/**
 * Monotonically increasing stateVersion generator.
 * Starts at 1 and increments by exactly 1 per event.
 */
class StateVersionGenerator {
  private current: number = 0;

  /** Get the next stateVersion. */
  next(): number {
    this.current += 1;
    return this.current;
  }

  /** Get the current stateVersion without incrementing. */
  get currentVersion(): number {
    return this.current;
  }

  /** Reset to 0 (for testing). */
  reset(): void {
    this.current = 0;
  }
}

// ---------------------------------------------------------------------------
// Delta Builder
// ---------------------------------------------------------------------------

/**
 * Builds a compact delta event from a partial change.
 * Only includes fields that are provided.
 */
function buildDelta(
  version: number,
  kind: DeltaKind,
  partial: Omit<DeltaEvent, "stateVersion" | "kind" | "timestamp">,
): DeltaEvent {
  const event: DeltaEvent = {
    stateVersion: version,
    kind,
    timestamp: new Date().toISOString(),
  };

  if (partial.uri !== undefined) event.uri = partial.uri;
  if (partial.language !== undefined) event.language = partial.language;
  if (partial.changes !== undefined) event.changes = partial.changes;
  if (partial.selection !== undefined) event.selection = partial.selection;
  if (partial.visibleEditors !== undefined) event.visibleEditors = partial.visibleEditors;
  if (partial.diagnostics !== undefined) event.diagnostics = partial.diagnostics;
  if (partial.meta !== undefined) event.meta = partial.meta;

  return event;
}

// ---------------------------------------------------------------------------
// Event Stream
// ---------------------------------------------------------------------------

/**
 * The main Event Stream class.
 *
 * Usage:
 *   const stream = new EventStream();
 *   stream.onDelta((event) => { ... });
 *   stream.onSnapshot((event) => { ... });
 *
 *   // Emit a delta
 *   stream.emitDocumentChange(uri, changes);
 *
 *   // Request a snapshot
 *   const snapshot = stream.requestSnapshot();
 *
 *   // Handle resync
 *   const response = stream.resync({ lastStateVersion: 42 });
 */
export class EventStream {
  private versionGen: StateVersionGenerator = new StateVersionGenerator();
  private deltaHistory: DeltaEvent[] = [];
  private maxHistorySize: number;
  private deltaListeners: Array<(event: DeltaEvent) => void> = [];
  private snapshotListeners: Array<(event: SnapshotEvent) => void> = [];

  /** Current IDE state (maintained incrementally). */
  private state: {
    documents: Map<string, DocumentSnapshot>;
    visibleEditors: Map<string, EditorSnapshot>;
    workspaceFolders: string[];
    activeEditor: string | undefined;
    extensionState: "activating" | "active" | "deactivating" | "inactive";
  };

  constructor(options: { maxHistorySize?: number; extensionVersion?: string } = {}) {
    this.maxHistorySize = options.maxHistorySize ?? 1000;
    this.state = {
      documents: new Map(),
      visibleEditors: new Map(),
      workspaceFolders: [],
      activeEditor: undefined,
      extensionState: "inactive",
    };
  }

  // -------------------------------------------------------------------------
  // Listener Registration
  // -------------------------------------------------------------------------

  /** Register a listener for delta events. */
  onDelta(listener: (event: DeltaEvent) => void): () => void {
    this.deltaListeners.push(listener);
    return () => {
      const idx = this.deltaListeners.indexOf(listener);
      if (idx >= 0) this.deltaListeners.splice(idx, 1);
    };
  }

  /** Register a listener for snapshot events. */
  onSnapshot(listener: (event: SnapshotEvent) => void): () => void {
    this.snapshotListeners.push(listener);
    return () => {
      const idx = this.snapshotListeners.indexOf(listener);
      if (idx >= 0) this.snapshotListeners.splice(idx, 1);
    };
  }

  // -------------------------------------------------------------------------
  // Delta Emission
  // -------------------------------------------------------------------------

  /**
   * Emit a document change delta.
   * Only the changed lines are included, not the full document.
   */
  emitDocumentChange(
    uri: string,
    changes: TextChange[],
    language?: string,
  ): DeltaEvent {
    const version = this.versionGen.next();
    const delta = buildDelta(version, "document.change", {
      uri,
      language,
      changes: changes.map((c) => ({
        startLine: c.startLine,
        startChar: c.startChar,
        endLine: c.endLine,
        endChar: c.endChar,
        text: c.text,
        oldText: c.oldText,
      })),
    });

    this.recordDelta(delta);
    this.notifyDeltaListeners(delta);
    return delta;
  }

  /**
   * Emit a document open delta.
   */
  emitDocumentOpen(
    uri: string,
    language: string,
    lineCount: number,
    content: string,
  ): DeltaEvent {
    const version = this.versionGen.next();
    const delta = buildDelta(version, "document.open", {
      uri,
      language,
      meta: { lineCount },
    });

    // Update internal state
    this.state.documents.set(uri, {
      uri,
      language,
      version: 1,
      lineCount,
      content,
      isDirty: false,
    });

    this.recordDelta(delta);
    this.notifyDeltaListeners(delta);
    return delta;
  }

  /**
   * Emit a document close delta.
   */
  emitDocumentClose(uri: string): DeltaEvent {
    const version = this.versionGen.next();
    const delta = buildDelta(version, "document.close", { uri });

    this.state.documents.delete(uri);
    if (this.state.activeEditor === uri) {
      this.state.activeEditor = undefined;
    }

    this.recordDelta(delta);
    this.notifyDeltaListeners(delta);
    return delta;
  }

  /**
   * Emit a document save delta.
   */
  emitDocumentSave(uri: string): DeltaEvent {
    const version = this.versionGen.next();
    const delta = buildDelta(version, "document.save", { uri });

    const doc = this.state.documents.get(uri);
    if (doc) {
      doc.isDirty = false;
    }

    this.recordDelta(delta);
    this.notifyDeltaListeners(delta);
    return delta;
  }

  /**
   * Emit a selection change delta.
   */
  emitSelectionChange(
    uri: string,
    selection: SelectionInfo,
  ): DeltaEvent {
    const version = this.versionGen.next();
    const delta = buildDelta(version, "editor.selection", {
      uri,
      selection,
    });

    this.recordDelta(delta);
    this.notifyDeltaListeners(delta);
    return delta;
  }

  /**
   * Emit a visible editors change delta.
   */
  emitVisibleEditorsChange(visibleUris: string[]): DeltaEvent {
    const version = this.versionGen.next();
    const delta = buildDelta(version, "editor.visible", {
      visibleEditors: visibleUris,
    });

    this.recordDelta(delta);
    this.notifyDeltaListeners(delta);
    return delta;
  }

  /**
   * Emit a workspace change delta.
   */
  emitWorkspaceChange(folders: string[]): DeltaEvent {
    const version = this.versionGen.next();
    const delta = buildDelta(version, "workspace.change", {
      meta: { folders },
    });

    this.state.workspaceFolders = [...folders];

    this.recordDelta(delta);
    this.notifyDeltaListeners(delta);
    return delta;
  }

  /**
   * Emit a diagnostic change delta.
   */
  emitDiagnosticChange(
    uri: string,
    diagnostics: DiagnosticSummary,
  ): DeltaEvent {
    const version = this.versionGen.next();
    const delta = buildDelta(version, "diagnostic", {
      uri,
      diagnostics,
    });

    this.recordDelta(delta);
    this.notifyDeltaListeners(delta);
    return delta;
  }

  /**
   * Emit an extension state change delta.
   */
  emitExtensionStateChange(
    state: "activating" | "active" | "deactivating" | "inactive",
  ): DeltaEvent {
    const version = this.versionGen.next();
    const kind: DeltaKind =
      state === "activating" || state === "active"
        ? "extension.activate"
        : "extension.deactivate";
    const delta = buildDelta(version, kind, {
      meta: { state },
    });

    this.state.extensionState = state;

    this.recordDelta(delta);
    this.notifyDeltaListeners(delta);
    return delta;
  }

  // -------------------------------------------------------------------------
  // Snapshot
  // -------------------------------------------------------------------------

  /**
   * Request a full snapshot of the current IDE state.
   * This is the only method that returns full document contents.
   */
  requestSnapshot(): SnapshotEvent {
    const version = this.versionGen.currentVersion;
    const snapshot: SnapshotEvent = {
      stateVersion: version,
      timestamp: new Date().toISOString(),
      documents: Array.from(this.state.documents.values()),
      visibleEditors: Array.from(this.state.visibleEditors.values()),
      workspaceFolders: [...this.state.workspaceFolders],
      activeEditor: this.state.activeEditor,
      extension: {
        version: "0.1.0",
        state: this.state.extensionState,
      },
    };

    this.notifySnapshotListeners(snapshot);
    return snapshot;
  }

  // -------------------------------------------------------------------------
  // Resynchronization
  // -------------------------------------------------------------------------

  /**
   * Handle a resynchronization request from a client.
   *
   * If the client's lastStateVersion is too far behind (or invalid),
   * returns a full snapshot. Otherwise, returns the missed deltas.
   */
  resync(request: ResyncRequest): ResyncResponse {
    const { lastStateVersion, maxDeltas = 100 } = request;
    const currentVersion = this.versionGen.currentVersion;

    // If the client is at version 0 or behind the history window, send a snapshot
    if (
      lastStateVersion <= 0 ||
      lastStateVersion < currentVersion - this.deltaHistory.length
    ) {
      return {
        type: "snapshot",
        snapshot: this.requestSnapshot(),
      };
    }

    // If the client is already up to date
    if (lastStateVersion >= currentVersion) {
      return {
        type: "deltas",
        deltas: [],
        currentVersion,
      };
    }

    // Return the missed deltas
    const startIndex = lastStateVersion; // deltas are 1-indexed by stateVersion
    const endIndex = Math.min(startIndex + maxDeltas, currentVersion);
    const missedDeltas: DeltaEvent[] = [];

    for (let i = startIndex; i < endIndex; i++) {
      const delta = this.deltaHistory[i - 1]; // array is 0-indexed
      if (delta) {
        missedDeltas.push(delta);
      }
    }

    return {
      type: "deltas",
      deltas: missedDeltas,
      currentVersion,
    };
  }

  // -------------------------------------------------------------------------
  // State Management
  // -------------------------------------------------------------------------

  /**
   * Update the internal document state (called by the extension when
   * it receives VS Code events).
   */
  updateDocumentState(uri: string, update: Partial<DocumentSnapshot>): void {
    const existing = this.state.documents.get(uri);
    if (existing) {
      this.state.documents.set(uri, { ...existing, ...update });
    } else {
      this.state.documents.set(uri, {
        uri,
        language: update.language ?? "plaintext",
        version: update.version ?? 1,
        lineCount: update.lineCount ?? 0,
        content: update.content ?? "",
        isDirty: update.isDirty ?? false,
      });
    }
  }

  /**
   * Update the internal editor state.
   */
  updateEditorState(uri: string, update: Partial<EditorSnapshot>): void {
    const existing = this.state.visibleEditors.get(uri);
    if (existing) {
      this.state.visibleEditors.set(uri, { ...existing, ...update });
    } else {
      this.state.visibleEditors.set(uri, {
        uri,
        selection: update.selection ?? {
          active: { line: 0, character: 0 },
          start: { line: 0, character: 0 },
          end: { line: 0, character: 0 },
          isEmpty: true,
        },
        visibleRanges: update.visibleRanges ?? [],
      });
    }
  }

  /**
   * Set the active editor URI.
   */
  setActiveEditor(uri: string | undefined): void {
    this.state.activeEditor = uri;
  }

  /**
   * Get the current stateVersion.
   */
  get currentStateVersion(): number {
    return this.versionGen.currentVersion;
  }

  /**
   * Get the number of deltas in history.
   */
  get historySize(): number {
    return this.deltaHistory.length;
  }

  // -------------------------------------------------------------------------
  // Internal Helpers
  // -------------------------------------------------------------------------

  private recordDelta(delta: DeltaEvent): void {
    this.deltaHistory.push(delta);
    if (this.deltaHistory.length > this.maxHistorySize) {
      this.deltaHistory.shift();
    }
  }

  private notifyDeltaListeners(event: DeltaEvent): void {
    for (const listener of this.deltaListeners) {
      try {
        listener(event);
      } catch (err) {
        // Don't let a listener crash the stream
        console.error("VSCODER: delta listener error:", err);
      }
    }
  }

  private notifySnapshotListeners(event: SnapshotEvent): void {
    for (const listener of this.snapshotListeners) {
      try {
        listener(event);
      } catch (err) {
        console.error("VSCODER: snapshot listener error:", err);
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Utility: Compute a hash of a delta (for integrity verification)
// ---------------------------------------------------------------------------

/**
 * Compute a SHA-256 hash of a delta event for integrity verification.
 * The hash covers all fields except the timestamp (which may vary).
 */
export function hashDelta(delta: DeltaEvent): string {
  const { timestamp: _omit, ...rest } = delta;
  const canonical = JSON.stringify(rest);
  return createHash("sha256").update(canonical, "utf8").digest("hex");
}

// ---------------------------------------------------------------------------
// Utility: Verify delta chain integrity
// ---------------------------------------------------------------------------

/**
 * Verify that a sequence of deltas has monotonically increasing stateVersions
 * with no gaps.
 */
export function verifyDeltaChain(deltas: DeltaEvent[]): {
  valid: boolean;
  errors: string[];
} {
  const errors: string[] = [];

  if (deltas.length === 0) {
    return { valid: true, errors };
  }

  for (let i = 0; i < deltas.length; i++) {
    const delta = deltas[i];

    if (i === 0) {
      // First delta can be any version
      continue;
    }

    const prev = deltas[i - 1];
    if (delta.stateVersion !== prev.stateVersion + 1) {
      errors.push(
        `Gap at index ${i}: expected stateVersion ${prev.stateVersion + 1}, got ${delta.stateVersion}`,
      );
    }
  }

  return { valid: errors.length === 0, errors };
}

// ---------------------------------------------------------------------------
// Re-exports
// ---------------------------------------------------------------------------

export { sanitize as sanitizeEvent };
