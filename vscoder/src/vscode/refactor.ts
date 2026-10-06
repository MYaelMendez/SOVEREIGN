/**
 * VSCODER:// Refactoring Engine
 *
 * Integrates with VS Code's Code Actions and WorkspaceEdit APIs to provide
 * a unified refactoring interface. All operations use vscode.executeCodeActionProvider
 * and workspace.applyEdit — no text-based search/replace.
 *
 * Primitives:
 *   - refactor.list       → enumerate available code actions for a range
 *   - refactor.apply      → apply a specific code action by title
 *   - refactor.extract    → extract refactorings (method, function, variable, const)
 *   - refactor.move       → move refactorings (to new file, between classes)
 *   - refactor.rewrite    → rewrite refactorings (convert function→class, add/remove param, etc.)
 *   - imports.organize    → organize imports (sort, remove unused)
 */

import * as vscode from 'vscode';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A serializable summary of a CodeAction (safe to pass across boundaries). */
export interface RefactorActionSummary {
  title: string;
  kind: string;
  isPreferred: boolean;
  hasEdit: boolean;
  hasCommand: boolean;
}

/** Result of a list operation. */
export interface RefactorListResult {
  uri: string;
  range: { start: { line: number; character: number }; end: { line: number; character: number } };
  actions: RefactorActionSummary[];
}

/** Result of an apply operation. */
export interface RefactorApplyResult {
  applied: boolean;
  title: string;
  editCount: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert a vscode.Range to a plain serializable object. */
function rangeToPlain(range: vscode.Range): { start: { line: number; character: number }; end: { line: number; character: number } } {
  return {
    start: { line: range.start.line, character: range.start.character },
    end: { line: range.end.line, character: range.end.character },
  };
}

/** Convert a CodeAction to a serializable summary. */
function actionToSummary(action: vscode.CodeAction): RefactorActionSummary {
  return {
    title: action.title,
    kind: action.kind?.value ?? '',
    isPreferred: action.isPreferred ?? false,
    hasEdit: action.edit !== undefined,
    hasCommand: action.command !== undefined,
  };
}

/**
 * Execute the built-in vscode.executeCodeActionProvider command.
 * This is the core primitive — it asks VS Code to gather all code actions
 * from all registered providers for the given document + range + kind.
 */
async function executeCodeActionProvider(
  uri: vscode.Uri,
  range: vscode.Range,
  kind?: vscode.CodeActionKind,
  token?: vscode.CancellationToken,
): Promise<vscode.CodeAction[]> {
  const args: unknown[] = [uri, range];
  if (kind) {
    args.push(kind.value);
  }
  if (token) {
    args.push(token);
  }
  const result = await vscode.commands.executeCommand<vscode.CodeAction[]>(
    'vscode.executeCodeActionProvider',
    ...args,
  );
  return result ?? [];
}

// ---------------------------------------------------------------------------
// refactor.list
// ---------------------------------------------------------------------------

/**
 * List all available refactoring code actions for the given range in the
 * specified document. Optionally filter by a specific CodeActionKind.
 */
export async function list(
  uri: vscode.Uri,
  range: vscode.Range,
  kind?: vscode.CodeActionKind,
  token?: vscode.CancellationToken,
): Promise<RefactorListResult> {
  const actions = await executeCodeActionProvider(uri, range, kind, token);
  return {
    uri: uri.toString(),
    range: rangeToPlain(range),
    actions: actions.map(actionToSummary),
  };
}

// ---------------------------------------------------------------------------
// refactor.apply
// ---------------------------------------------------------------------------

/**
 * Apply a specific code action by its title. The action is looked up among
 * the code actions available for the given range, and if found, its
 * WorkspaceEdit is applied via workspace.applyEdit.
 *
 * Returns whether the action was found and applied.
 */
export async function apply(
  uri: vscode.Uri,
  range: vscode.Range,
  title: string,
  kind?: vscode.CodeActionKind,
  token?: vscode.CancellationToken,
): Promise<RefactorApplyResult> {
  const actions = await executeCodeActionProvider(uri, range, kind, token);
  const match = actions.find((a) => a.title === title);
  if (!match) {
    return { applied: false, title, editCount: 0 };
  }
  if (match.edit) {
    const ok = await vscode.workspace.applyEdit(match.edit);
    return { applied: ok, title, editCount: match.edit.size };
  }
  // Action has no edit (command-only) — nothing to apply via WorkspaceEdit.
  return { applied: true, title, editCount: 0 };
}

// ---------------------------------------------------------------------------
// refactor.extract
// ---------------------------------------------------------------------------

/**
 * Get extract refactoring actions (refactor.extract kind).
 * Includes: Extract Method, Extract Function, Extract Variable, Extract Constant,
 * Extract Interface, etc.
 */
export async function extract(
  uri: vscode.Uri,
  range: vscode.Range,
  token?: vscode.CancellationToken,
): Promise<RefactorListResult> {
  return list(uri, range, vscode.CodeActionKind.RefactorExtract, token);
}

// ---------------------------------------------------------------------------
// refactor.move
// ---------------------------------------------------------------------------

/**
 * Get move refactoring actions (refactor.move kind).
 * Includes: Move to new file, Move property between classes, Move method to base class, etc.
 */
export async function move(
  uri: vscode.Uri,
  range: vscode.Range,
  token?: vscode.CancellationToken,
): Promise<RefactorListResult> {
  return list(uri, range, vscode.CodeActionKind.RefactorMove, token);
}

// ---------------------------------------------------------------------------
// refactor.rewrite
// ---------------------------------------------------------------------------

/**
 * Get rewrite refactoring actions (refactor.rewrite kind).
 * Includes: Convert function to class, Add/Remove parameter, Encapsulate field,
 * Make method static, etc.
 */
export async function rewrite(
  uri: vscode.Uri,
  range: vscode.Range,
  token?: vscode.CancellationToken,
): Promise<RefactorListResult> {
  return list(uri, range, vscode.CodeActionKind.RefactorRewrite, token);
}

// ---------------------------------------------------------------------------
// imports.organize
// ---------------------------------------------------------------------------

/**
 * Organize imports in the given document (source.organizeImports kind).
 * This sorts imports and removes unused ones.
 *
 * Returns the list of organize-imports actions found. If an action has an
 * edit, it is NOT automatically applied — call apply() with the action title
 * to apply it.
 */
export async function organizeImports(
  uri: vscode.Uri,
  token?: vscode.CancellationToken,
): Promise<RefactorListResult> {
  // For organize imports, we use the full document range.
  const doc = await vscode.workspace.openTextDocument(uri);
  const fullRange = new vscode.Range(
    doc.positionAt(0),
    doc.positionAt(doc.getText().length),
  );
  return list(uri, fullRange, vscode.CodeActionKind.SourceOrganizeImports, token);
}

/**
 * Apply the first available organize-imports action. Returns whether an
 * action was found and applied.
 */
export async function applyOrganizeImports(
  uri: vscode.Uri,
  token?: vscode.CancellationToken,
): Promise<RefactorApplyResult> {
  const doc = await vscode.workspace.openTextDocument(uri);
  const fullRange = new vscode.Range(
    doc.positionAt(0),
    doc.positionAt(doc.getText().length),
  );
  const actions = await executeCodeActionProvider(
    uri,
    fullRange,
    vscode.CodeActionKind.SourceOrganizeImports,
    token,
  );
  if (actions.length === 0) {
    return { applied: false, title: '(organize imports)', editCount: 0 };
  }
  // Prefer the first action (usually the only one).
  const target = actions[0];
  if (target.edit) {
    const ok = await vscode.workspace.applyEdit(target.edit);
    return { applied: ok, title: target.title, editCount: target.edit.size };
  }
  return { applied: true, title: target.title, editCount: 0 };
}

// ---------------------------------------------------------------------------
// Convenience: list all refactorings (no kind filter)
// ---------------------------------------------------------------------------

/**
 * List ALL refactoring code actions available for the given range,
 * regardless of kind. This is the broadest query.
 */
export async function listAll(
  uri: vscode.Uri,
  range: vscode.Range,
  token?: vscode.CancellationToken,
): Promise<RefactorListResult> {
  return list(uri, range, undefined, token);
}
