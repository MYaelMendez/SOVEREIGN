/**
 * VSCODER:// Command Resolver — Phase 2 Bridge
 *
 * Resolves every command to a capability/effect class, classifies the effect
 * as LOCAL / DURABLE / EXTERNAL, denies unknown commands (fail closed), and
 * ensures authority follows effect not entrypoint.
 *
 * Core invariants:
 *   1. git.push via any entrypoint (terminal.run, task.run, ide.executeCommand,
 *      SCM push) all resolve to EXTERNAL.
 *   2. ui.executeCommand(anything) never resolves to LOCAL.
 *   3. Unknown commands are denied (fail closed).
 *   4. Authority follows effect, not entrypoint.
 *
 * Self-contained: no imports from other VSCODER modules.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Entrypoint — the mechanism used to invoke a command. */
export type Entrypoint =
  | "terminal.run"
  | "task.run"
  | "ide.executeCommand"
  | "scm.push"
  | "ui.executeCommand";

/** Effect classification — what the command actually does. */
export type Effect = "LOCAL" | "DURABLE" | "EXTERNAL";

/** A resolved capability with its effect classification. */
export interface Capability {
  /** Canonical capability name, e.g. "git.push". */
  name: string;
  /** Effect classification. */
  effect: Effect;
  /** Human-readable description. */
  description: string;
}

/** The result of resolving a command via an entrypoint. */
export interface Resolution {
  /** The entrypoint used. */
  entrypoint: Entrypoint;
  /** The command that was invoked. */
  command: string;
  /** The resolved capability. */
  capability: Capability;
  /** The final effect classification (after entrypoint constraints). */
  effect: Effect;
  /** Whether the command is known and allowed to be considered. */
  granted: boolean;
  /** Whether user confirmation is required (DURABLE and EXTERNAL). */
  requiresConfirmation: boolean;
  /** Whether a passkey is required (EXTERNAL only). */
  requiresPasskey: boolean;
  /** Human-readable explanation of the resolution. */
  reason: string;
}

/** Entrypoint definition with its constraints. */
interface EntrypointDef {
  /** Minimum effect level for this entrypoint. */
  minEffect: Effect;
  /** Whether this entrypoint only allows EXTERNAL commands. */
  externalOnly: boolean;
  /** Human-readable description. */
  description: string;
}

// ---------------------------------------------------------------------------
// Capability Registry
// ---------------------------------------------------------------------------

/**
 * Registry of all known commands and their capabilities.
 * Unknown commands are NOT in this registry and will be denied.
 */
const CAPABILITIES: Record<string, Capability> = {
  // ── Git operations ──────────────────────────────────────────────────────
  "git.push": {
    name: "git.push",
    effect: "EXTERNAL",
    description: "Push commits to remote repository",
  },
  "git.commit": {
    name: "git.commit",
    effect: "DURABLE",
    description: "Commit changes to local repository",
  },
  "git.diff": {
    name: "git.diff",
    effect: "LOCAL",
    description: "Show diff of changes",
  },
  "git.status": {
    name: "git.status",
    effect: "LOCAL",
    description: "Show working tree status",
  },
  "git.branch": {
    name: "git.branch",
    effect: "DURABLE",
    description: "Create or switch branches",
  },
  "git.merge": {
    name: "git.merge",
    effect: "DURABLE",
    description: "Merge branches",
  },
  "git.reset": {
    name: "git.reset",
    effect: "DURABLE",
    description: "Reset current branch",
  },
  "git.clone": {
    name: "git.clone",
    effect: "EXTERNAL",
    description: "Clone remote repository",
  },
  "git.fetch": {
    name: "git.fetch",
    effect: "EXTERNAL",
    description: "Fetch from remote repository",
  },
  "git.pull": {
    name: "git.pull",
    effect: "EXTERNAL",
    description: "Pull from remote repository",
  },

  // ── Filesystem operations ───────────────────────────────────────────────
  "fs.read": {
    name: "fs.read",
    effect: "LOCAL",
    description: "Read file contents",
  },
  "fs.write": {
    name: "fs.write",
    effect: "DURABLE",
    description: "Write file contents",
  },
  "fs.delete": {
    name: "fs.delete",
    effect: "DURABLE",
    description: "Delete file",
  },
  "fs.rename": {
    name: "fs.rename",
    effect: "DURABLE",
    description: "Rename file",
  },

  // ── Build / Test / Debug ────────────────────────────────────────────────
  "build.run": {
    name: "build.run",
    effect: "LOCAL",
    description: "Run build task",
  },
  "test.run": {
    name: "test.run",
    effect: "LOCAL",
    description: "Run tests",
  },
  "debug.start": {
    name: "debug.start",
    effect: "LOCAL",
    description: "Start debug session",
  },

  // ── Refactoring ─────────────────────────────────────────────────────────
  "refactor.apply": {
    name: "refactor.apply",
    effect: "DURABLE",
    description: "Apply refactoring",
  },
  "refactor.list": {
    name: "refactor.list",
    effect: "LOCAL",
    description: "List available refactorings",
  },

  // ── Symbol operations ───────────────────────────────────────────────────
  "symbol.find": {
    name: "symbol.find",
    effect: "LOCAL",
    description: "Find symbol definition",
  },
  "symbol.references": {
    name: "symbol.references",
    effect: "LOCAL",
    description: "Find symbol references",
  },
  "symbol.rename": {
    name: "symbol.rename",
    effect: "DURABLE",
    description: "Rename symbol",
  },
  "workspace.symbols": {
    name: "workspace.symbols",
    effect: "LOCAL",
    description: "Search workspace symbols",
  },

  // ── Diagnostics ─────────────────────────────────────────────────────────
  "diagnostics.read": {
    name: "diagnostics.read",
    effect: "LOCAL",
    description: "Read diagnostics",
  },

  // ── Network ─────────────────────────────────────────────────────────────
  "http.fetch": {
    name: "http.fetch",
    effect: "EXTERNAL",
    description: "HTTP request",
  },

  // ── Benchmark ───────────────────────────────────────────────────────────
  "benchmark.run": {
    name: "benchmark.run",
    effect: "LOCAL",
    description: "Run benchmark",
  },

  // ── Receipts ────────────────────────────────────────────────────────────
  "receipt.generate": {
    name: "receipt.generate",
    effect: "DURABLE",
    description: "Generate receipt",
  },
  "receipt.verify": {
    name: "receipt.verify",
    effect: "LOCAL",
    description: "Verify receipt chain",
  },
};

// ---------------------------------------------------------------------------
// Entrypoint Registry
// ---------------------------------------------------------------------------

/**
 * Registry of all known entrypoints and their constraints.
 *
 * minEffect: the minimum effect level for commands invoked via this entrypoint.
 *   - terminal.run, task.run, ide.executeCommand: LOCAL (no upgrade)
 *   - ui.executeCommand: DURABLE (never LOCAL)
 *   - scm.push: EXTERNAL (always EXTERNAL)
 *
 * externalOnly: if true, only EXTERNAL commands are allowed via this entrypoint.
 */
const ENTRYPOINTS: Record<Entrypoint, EntrypointDef> = {
  "terminal.run": {
    minEffect: "LOCAL",
    externalOnly: false,
    description: "Run shell command in terminal",
  },
  "task.run": {
    minEffect: "LOCAL",
    externalOnly: false,
    description: "Run VS Code task",
  },
  "ide.executeCommand": {
    minEffect: "LOCAL",
    externalOnly: false,
    description: "Execute VS Code command",
  },
  "scm.push": {
    minEffect: "EXTERNAL",
    externalOnly: true,
    description: "SCM push operation",
  },
  "ui.executeCommand": {
    minEffect: "DURABLE",
    externalOnly: false,
    description: "UI command execution (never LOCAL)",
  },
};

// ---------------------------------------------------------------------------
// Effect ordering for comparison
// ---------------------------------------------------------------------------

const EFFECT_ORDER: Record<Effect, number> = {
  LOCAL: 0,
  DURABLE: 1,
  EXTERNAL: 2,
};

// ---------------------------------------------------------------------------
// Resolution Engine
// ---------------------------------------------------------------------------

/**
 * Resolve a command via an entrypoint to a capability and effect classification.
 *
 * Algorithm:
 *   1. Look up the entrypoint — deny if unknown.
 *   2. Look up the command in the capability registry — deny if unknown.
 *   3. If the entrypoint is externalOnly, deny non-EXTERNAL commands.
 *   4. Apply the entrypoint's minimum effect (upgrade LOCAL → DURABLE → EXTERNAL).
 *   5. Return the resolution with authorization requirements.
 */
export function resolve(entrypoint: Entrypoint, command: string): Resolution {
  // 1. Check entrypoint
  const ep = ENTRYPOINTS[entrypoint];
  if (!ep) {
    return deny(entrypoint, command, `Unknown entrypoint: ${entrypoint}`);
  }

  // 2. Check command
  const cap = CAPABILITIES[command];
  if (!cap) {
    return deny(entrypoint, command, `Unknown command: ${command}`);
  }

  // 3. External-only entrypoint check
  if (ep.externalOnly && cap.effect !== "EXTERNAL") {
    return deny(
      entrypoint,
      command,
      `Entrypoint '${entrypoint}' only allows EXTERNAL commands, got ${cap.effect}`
    );
  }

  // 4. Apply entrypoint minimum effect
  const effect = upgradeEffect(cap.effect, ep.minEffect);

  // 5. Build resolution
  return {
    entrypoint,
    command,
    capability: cap,
    effect,
    granted: true,
    requiresConfirmation: effect === "DURABLE" || effect === "EXTERNAL",
    requiresPasskey: effect === "EXTERNAL",
    reason:
      effect === cap.effect
        ? `Resolved ${command} via ${entrypoint} → ${effect}`
        : `Resolved ${command} via ${entrypoint} → ${effect} (upgraded from ${cap.effect})`,
  };
}

/**
 * Resolve multiple commands at once.
 * Returns resolutions in the same order as the input.
 */
export function resolveAll(
  commands: Array<{ entrypoint: Entrypoint; command: string }>
): Resolution[] {
  return commands.map((c) => resolve(c.entrypoint, c.command));
}

/**
 * Check if a command is known (in the capability registry).
 */
export function isKnownCommand(command: string): boolean {
  return command in CAPABILITIES;
}

/**
 * Check if an entrypoint is known.
 */
export function isKnownEntrypoint(entrypoint: string): entrypoint is Entrypoint {
  return entrypoint in ENTRYPOINTS;
}

/**
 * Get all known commands.
 */
export function getKnownCommands(): string[] {
  return Object.keys(CAPABILITIES);
}

/**
 * Get all known entrypoints.
 */
export function getKnownEntrypoints(): Entrypoint[] {
  return Object.keys(ENTRYPOINTS) as Entrypoint[];
}

/**
 * Get the capability for a known command, or null if unknown.
 */
export function getCapability(command: string): Capability | null {
  return CAPABILITIES[command] ?? null;
}

// ---------------------------------------------------------------------------
// Internal Helpers
// ---------------------------------------------------------------------------

/**
 * Upgrade an effect to a minimum level.
 * Returns the higher of the two effects.
 */
function upgradeEffect(current: Effect, minimum: Effect): Effect {
  return EFFECT_ORDER[current] >= EFFECT_ORDER[minimum] ? current : minimum;
}

/**
 * Build a denial resolution.
 */
function deny(entrypoint: Entrypoint, command: string, reason: string): Resolution {
  return {
    entrypoint,
    command,
    capability: {
      name: "unknown",
      effect: "EXTERNAL",
      description: "Unknown or denied",
    },
    effect: "EXTERNAL",
    granted: false,
    requiresConfirmation: true,
    requiresPasskey: true,
    reason,
  };
}

// ---------------------------------------------------------------------------
// Re-exports for convenience
// ---------------------------------------------------------------------------

export const resolver = {
  resolve,
  resolveAll,
  isKnownCommand,
  isKnownEntrypoint,
  getKnownCommands,
  getKnownEntrypoints,
  getCapability,
};
