/**
 * VSCODER:// Plan Validity Contract — plan.ts
 *
 * A plan captures the expected workspace state at planning time. Before any
 * mutation is applied, the current workspace state is compared against the
 * plan's precondition. If the state has diverged, the mutation is rejected
 * with a 409 PLAN_STATE_CONFLICT error.
 *
 * Invalidation triggers:
 *   1. Human-edit invalidation   – a relevant file was modified after planning
 *   2. Branch/HEAD invalidation   – the git branch or HEAD commit changed
 *   3. Relevant-file mutation    – any tracked file's content hash changed
 *
 * Self-contained: uses only Node.js built-ins (crypto). No external deps.
 */

import { createHash } from "crypto";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** SHA-256 hex digest (64 lowercase hex characters). */
export type Hash = string;

/** A single relevant file entry in the plan. */
export interface RelevantFile {
  /** Workspace-relative path, e.g. "src/bridge/plan.ts". */
  path: string;
  /** SHA-256 of the file content at planning time. */
  hash: Hash;
}

/** Expected workspace state captured when the plan was created. */
export interface ExpectedState {
  /** SHA-256 over the canonical workspace snapshot (all relevant files + git state). */
  workspaceHash: Hash;
  /** Git branch name at planning time, e.g. "main". */
  branch: string;
  /** Git HEAD commit SHA at planning time. */
  head: string;
  /** Whether the working tree had uncommitted changes at planning time. */
  dirtyState: boolean;
  /** Per-file hashes for every file the plan depends on. */
  relevantFiles: RelevantFile[];
}

/** A plan: intent + expected precondition state. */
export interface Plan {
  /** Unique plan identifier. */
  id: string;
  /** Human-readable description of what the plan intends to do. */
  intent: string;
  /** The expected workspace state that must hold before mutations apply. */
  expectedState: ExpectedState;
  /** Epoch milliseconds when the plan was created. */
  createdAt: number;
}

/** Current workspace state observed at validation time. */
export interface CurrentState {
  workspaceHash: Hash;
  branch: string;
  head: string;
  dirtyState: boolean;
  relevantFiles: RelevantFile[];
}

/** Result of validating a plan against current workspace state. */
export interface ValidationResult {
  /** True if the plan is still valid (current state matches expected). */
  valid: boolean;
  /** Human-readable reasons for invalidation (empty when valid). */
  reasons: string[];
  /** Structured conflict details (null when valid). */
  conflict?: PlanStateConflict;
}

/** Structured conflict information for 409 PLAN_STATE_CONFLICT. */
export interface PlanStateConflict {
  /** HTTP-style status code (always 409). */
  status: 409;
  /** Machine-readable error code. */
  code: "PLAN_STATE_CONFLICT";
  /** Human-readable summary. */
  message: string;
  /** Which precondition(s) failed. */
  failedChecks: ConflictKind[];
  /** The plan that was invalidated. */
  planId: string;
  /** Expected state from the plan. */
  expected: ExpectedState;
  /** Observed current state. */
  current: CurrentState;
}

/** Kinds of conflicts that can invalidate a plan. */
export type ConflictKind =
  | "WORKSPACE_HASH_MISMATCH"
  | "BRANCH_CHANGED"
  | "HEAD_CHANGED"
  | "DIRTY_STATE_CHANGED"
  | "RELEVANT_FILE_MUTATED";

// ---------------------------------------------------------------------------
// PlanStateConflictError
// ---------------------------------------------------------------------------

/**
 * Error thrown when a plan's precondition no longer holds.
 * Carries a structured PlanStateConflict payload for the 409 response.
 */
export class PlanStateConflictError extends Error {
  readonly conflict: PlanStateConflict;

  constructor(conflict: PlanStateConflict) {
    super(conflict.message);
    this.name = "PlanStateConflictError";
    this.conflict = conflict;
    // Maintain prototype chain for instanceof checks
    Object.setPrototypeOf(this, PlanStateConflictError.prototype);
  }
}

// ---------------------------------------------------------------------------
// Hashing helpers
// ---------------------------------------------------------------------------

/** SHA-256 of a string. */
function sha256(value: string): Hash {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

/** SHA-256 of a Buffer. */
function sha256Buffer(buf: Buffer): Hash {
  return createHash("sha256").update(buf).digest("hex");
}

/** Deterministic JSON serialisation (sorted keys, no whitespace). */
function canonicalJson(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) {
    return "[" + value.map(canonicalJson).join(",") + "]";
  }
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  const pairs = keys.map(
    (k) => JSON.stringify(k) + ":" + canonicalJson(obj[k])
  );
  return "{" + pairs.join(",") + "}";
}

/** Compute the workspace hash from git state + relevant file hashes. */
function computeWorkspaceHash(state: {
  branch: string;
  head: string;
  dirtyState: boolean;
  relevantFiles: RelevantFile[];
}): Hash {
  // Sort by path for determinism
  const sorted = [...state.relevantFiles].sort((a, b) =>
    a.path < b.path ? -1 : a.path > b.path ? 1 : 0
  );
  const canonical = canonicalJson({
    branch: state.branch,
    head: state.head,
    dirtyState: state.dirtyState,
    files: sorted.map((f) => ({ path: f.path, hash: f.hash })),
  });
  return sha256(canonical);
}

// ---------------------------------------------------------------------------
// PlanBuilder
// ---------------------------------------------------------------------------

/**
 * Builder for constructing a Plan with its expected state.
 *
 * Usage:
 *   const plan = new PlanBuilder("Refactor auth module")
 *     .withGitState("main", "abc123", false)
 *     .withRelevantFile("src/auth.ts", fileBuffer)
 *     .withRelevantFile("src/session.ts", fileBuffer)
 *     .build();
 */
export class PlanBuilder {
  private _id: string;
  private _intent: string;
  private _branch: string | null = null;
  private _head: string | null = null;
  private _dirtyState: boolean | null = null;
  private _relevantFiles: RelevantFile[] = [];
  private _createdAt: number;

  constructor(intent: string, id?: string) {
    this._intent = intent;
    this._id = id ?? `plan_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
    this._createdAt = Date.now();
  }

  /** Set the git branch, HEAD, and dirty state. */
  withGitState(branch: string, head: string, dirtyState: boolean): this {
    this._branch = branch;
    this._head = head;
    this._dirtyState = dirtyState;
    return this;
  }

  /** Add a relevant file with its content buffer (hash computed automatically). */
  withRelevantFile(path: string, content: Buffer | string): this {
    const hash =
      typeof content === "string" ? sha256(content) : sha256Buffer(content);
    this._relevantFiles.push({ path, hash });
    return this;
  }

  /** Add a relevant file with a pre-computed hash. */
  withRelevantFileHash(path: string, hash: Hash): this {
    this._relevantFiles.push({ path, hash });
    return this;
  }

  /** Set the creation timestamp (defaults to now). */
  withCreatedAt(createdAt: number): this {
    this._createdAt = createdAt;
    return this;
  }

  /** Build the Plan. Throws if required fields are missing. */
  build(): Plan {
    if (this._branch === null) {
      throw new Error("PlanBuilder: branch is required (call withGitState)");
    }
    if (this._head === null) {
      throw new Error("PlanBuilder: head is required (call withGitState)");
    }
    if (this._dirtyState === null) {
      throw new Error("PlanBuilder: dirtyState is required (call withGitState)");
    }

    const expectedState: ExpectedState = {
      workspaceHash: "", // computed below
      branch: this._branch,
      head: this._head,
      dirtyState: this._dirtyState,
      relevantFiles: [...this._relevantFiles],
    };
    expectedState.workspaceHash = computeWorkspaceHash(expectedState);

    return {
      id: this._id,
      intent: this._intent,
      expectedState,
      createdAt: this._createdAt,
    };
  }
}

// ---------------------------------------------------------------------------
// PlanValidator
// ---------------------------------------------------------------------------

/**
 * Validates a plan against the current workspace state.
 *
 * Checks (in order):
 *   1. Branch match       – current branch must equal expected branch
 *   2. HEAD match         – current HEAD must equal expected HEAD
 *   3. Dirty-state match  – dirty flag must match (human edits flip this)
 *   4. Relevant-file hash – every relevant file's hash must match
 *   5. Workspace hash     – aggregate hash must match (catches anything above)
 *
 * If any check fails, the plan is invalid and a PlanStateConflictError
 * (or ValidationResult with valid=false) is returned.
 */
export class PlanValidator {
  /**
   * Validate a plan against current state.
   * Returns a ValidationResult (never throws).
   */
  validate(plan: Plan, current: CurrentState): ValidationResult {
    const reasons: string[] = [];
    const failedChecks: ConflictKind[] = [];

    // 1. Branch check
    if (current.branch !== plan.expectedState.branch) {
      failedChecks.push("BRANCH_CHANGED");
      reasons.push(
        `Branch changed: expected '${plan.expectedState.branch}', got '${current.branch}'`
      );
    }

    // 2. HEAD check
    if (current.head !== plan.expectedState.head) {
      failedChecks.push("HEAD_CHANGED");
      reasons.push(
        `HEAD changed: expected '${plan.expectedState.head}', got '${current.head}'`
      );
    }

    // 3. Dirty-state check
    if (current.dirtyState !== plan.expectedState.dirtyState) {
      failedChecks.push("DIRTY_STATE_CHANGED");
      reasons.push(
        `Dirty state changed: expected ${plan.expectedState.dirtyState}, got ${current.dirtyState}`
      );
    }

    // 4. Relevant-file mutation check
    const expectedFiles = new Map(
      plan.expectedState.relevantFiles.map((f) => [f.path, f.hash])
    );
    const currentFiles = new Map(
      current.relevantFiles.map((f) => [f.path, f.hash])
    );

    // Check for mutated or missing files
    for (const [path, expectedHash] of expectedFiles) {
      const currentHash = currentFiles.get(path);
      if (currentHash === undefined) {
        failedChecks.push("RELEVANT_FILE_MUTATED");
        reasons.push(`Relevant file missing: '${path}'`);
      } else if (currentHash !== expectedHash) {
        failedChecks.push("RELEVANT_FILE_MUTATED");
        reasons.push(
          `Relevant file mutated: '${path}' (expected ${expectedHash.slice(0, 12)}…, got ${currentHash.slice(0, 12)}…)`
        );
      }
    }

    // Check for new files not in the plan (also a mutation)
    for (const [path, currentHash] of currentFiles) {
      if (!expectedFiles.has(path)) {
        failedChecks.push("RELEVANT_FILE_MUTATED");
        reasons.push(
          `New relevant file appeared: '${path}' (hash ${currentHash.slice(0, 12)}…)`
        );
      }
    }

    // 5. Aggregate workspace hash check (catches anything above)
    const currentWorkspaceHash = computeWorkspaceHash(current);
    if (currentWorkspaceHash !== plan.expectedState.workspaceHash) {
      // Only add this if no more specific check already failed
      if (failedChecks.length === 0) {
        failedChecks.push("WORKSPACE_HASH_MISMATCH");
        reasons.push(
          `Workspace hash mismatch: expected ${plan.expectedState.workspaceHash.slice(0, 12)}…, got ${currentWorkspaceHash.slice(0, 12)}…`
        );
      }
    }

    const valid = failedChecks.length === 0;
    return {
      valid,
      reasons,
      conflict: valid
        ? undefined
        : {
            status: 409,
            code: "PLAN_STATE_CONFLICT",
            message: `Plan '${plan.id}' is invalid: ${reasons.join("; ")}`,
            failedChecks,
            planId: plan.id,
            expected: plan.expectedState,
            current,
          },
    };
  }

  /**
   * Validate a plan and throw PlanStateConflictError if invalid.
   * Use this in mutation code paths that need to reject on conflict.
   */
  assertValid(plan: Plan, current: CurrentState): void {
    const result = this.validate(plan, current);
    if (!result.valid) {
      throw new PlanStateConflictError(result.conflict!);
    }
  }
}

// ---------------------------------------------------------------------------
// Convenience: build CurrentState from raw inputs
// ---------------------------------------------------------------------------

/**
 * Build a CurrentState from git info and file buffers.
 * Computes all hashes automatically.
 */
export function buildCurrentState(options: {
  branch: string;
  head: string;
  dirtyState: boolean;
  files: Array<{ path: string; content: Buffer | string }>;
}): CurrentState {
  const relevantFiles: RelevantFile[] = options.files.map((f) => ({
    path: f.path,
    hash:
      typeof f.content === "string"
        ? sha256(f.content)
        : sha256Buffer(f.content),
  }));

  const state: CurrentState = {
    workspaceHash: "", // computed below
    branch: options.branch,
    head: options.head,
    dirtyState: options.dirtyState,
    relevantFiles,
  };
  state.workspaceHash = computeWorkspaceHash(state);
  return state;
}

// ---------------------------------------------------------------------------
// Re-exports
// ---------------------------------------------------------------------------

export { computeWorkspaceHash, canonicalJson, sha256, sha256Buffer };
