/**
 * VSCODER:// Language Server Protocol Integration
 *
 * Integrates with VS Code's built-in language services to provide
 * symbol navigation, renaming, workspace-wide symbol search, and
 * diagnostics reading. All operations use vscode.execute*Provider
 * commands — no text-based search.
 *
 * Primitives:
 *   - symbol.find          → find definition of a symbol at a position
 *   - symbol.references    → find all references to a symbol
 *   - symbol.rename        → rename a symbol across the workspace
 *   - workspace.symbols    → search symbols across the entire workspace
 *   - diagnostics.read     → read diagnostics for a document or workspace
 */

import * as vscode from 'vscode';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A serializable location (URI + range). */
export interface LocationInfo {
  uri: string;
  range: { start: { line: number; character: number }; end: { line: number; character: number } };
}

/** A serializable symbol information entry. */
export interface SymbolInfo {
  name: string;
  kind: string;
  detail?: string;
  location: LocationInfo;
  containerName?: string;
}

/** A serializable workspace symbol entry. */
export interface WorkspaceSymbolInfo {
  name: string;
  kind: string;
  location: LocationInfo;
  containerName?: string;
}

/** A serializable diagnostic entry. */
export interface DiagnosticInfo {
  message: string;
  severity: string;
  range: { start: { line: number; character: number }; end: { line: number; character: number } };
  source?: string;
  code?: string | number;
}

/** Result of a symbol.find operation. */
export interface SymbolFindResult {
  uri: string;
  position: { line: number; character: number };
  definitions: LocationInfo[];
}

/** Result of a symbol.references operation. */
export interface SymbolReferencesResult {
  uri: string;
  position: { line: number; character: number };
  references: LocationInfo[];
  declaration?: LocationInfo;
}

/** Result of a symbol.rename operation. */
export interface SymbolRenameResult {
  uri: string;
  position: { line: number; character: number };
  oldName: string;
  newName: string;
  changed: boolean;
  editCount: number;
}

/** Result of a workspace.symbols operation. */
export interface WorkspaceSymbolsResult {
  query: string;
  symbols: WorkspaceSymbolInfo[];
}

/** Result of a diagnostics.read operation. */
export interface DiagnosticsReadResult {
  uri?: string;
  diagnostics: DiagnosticInfo[];
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

/** Convert a vscode.Location to a serializable LocationInfo. */
function locationToInfo(location: vscode.Location): LocationInfo {
  return {
    uri: location.uri.toString(),
    range: rangeToPlain(location.range),
  };
}

/** Convert a vscode.SymbolKind to a string. */
function symbolKindToString(kind: vscode.SymbolKind): string {
  const kinds: Record<number, string> = {
    [vscode.SymbolKind.File]: 'File',
    [vscode.SymbolKind.Module]: 'Module',
    [vscode.SymbolKind.Namespace]: 'Namespace',
    [vscode.SymbolKind.Package]: 'Package',
    [vscode.SymbolKind.Class]: 'Class',
    [vscode.SymbolKind.Method]: 'Method',
    [vscode.SymbolKind.Property]: 'Property',
    [vscode.SymbolKind.Field]: 'Field',
    [vscode.SymbolKind.Constructor]: 'Constructor',
    [vscode.SymbolKind.Enum]: 'Enum',
    [vscode.SymbolKind.Interface]: 'Interface',
    [vscode.SymbolKind.Function]: 'Function',
    [vscode.SymbolKind.Variable]: 'Variable',
    [vscode.SymbolKind.Constant]: 'Constant',
    [vscode.SymbolKind.String]: 'String',
    [vscode.SymbolKind.Number]: 'Number',
    [vscode.SymbolKind.Boolean]: 'Boolean',
    [vscode.SymbolKind.Array]: 'Array',
    [vscode.SymbolKind.Object]: 'Object',
    [vscode.SymbolKind.Key]: 'Key',
    [vscode.SymbolKind.Null]: 'Null',
    [vscode.SymbolKind.EnumMember]: 'EnumMember',
    [vscode.SymbolKind.Struct]: 'Struct',
    [vscode.SymbolKind.Event]: 'Event',
    [vscode.SymbolKind.Operator]: 'Operator',
    [vscode.SymbolKind.TypeParameter]: 'TypeParameter',
  };
  return kinds[kind] ?? 'Unknown';
}

/** Convert a vscode.DiagnosticSeverity to a string. */
function severityToString(severity: vscode.DiagnosticSeverity): string {
  const severities: Record<number, string> = {
    [vscode.DiagnosticSeverity.Error]: 'Error',
    [vscode.DiagnosticSeverity.Warning]: 'Warning',
    [vscode.DiagnosticSeverity.Information]: 'Information',
    [vscode.DiagnosticSeverity.Hint]: 'Hint',
  };
  return severities[severity] ?? 'Unknown';
}

/** Convert a vscode.SymbolInformation to a serializable WorkspaceSymbolInfo. */
function symbolInfoToWorkspace(info: vscode.SymbolInformation): WorkspaceSymbolInfo {
  return {
    name: info.name,
    kind: symbolKindToString(info.kind),
    location: locationToInfo(info.location),
    containerName: info.containerName,
  };
}

/** Convert a vscode.DocumentSymbol to a serializable SymbolInfo. */
function documentSymbolToInfo(symbol: vscode.DocumentSymbol): SymbolInfo {
  return {
    name: symbol.name,
    kind: symbolKindToString(symbol.kind),
    detail: symbol.detail,
    location: {
      uri: '',
      range: rangeToPlain(symbol.range),
    },
  };
}

/** Convert a vscode.Diagnostic to a serializable DiagnosticInfo. */
function diagnosticToInfo(diagnostic: vscode.Diagnostic): DiagnosticInfo {
  return {
    message: diagnostic.message,
    severity: severityToString(diagnostic.severity),
    range: rangeToPlain(diagnostic.range),
    source: diagnostic.source,
    code: typeof diagnostic.code === 'object' ? diagnostic.code.value : diagnostic.code,
  };
}

// ---------------------------------------------------------------------------
// symbol.find
// ---------------------------------------------------------------------------

/**
 * Find the definition of a symbol at the given position in the document.
 * Uses vscode.executeDefinitionProvider.
 */
export async function find(
  uri: vscode.Uri,
  position: vscode.Position,
): Promise<SymbolFindResult> {
  const locations = await vscode.commands.executeCommand<vscode.Location[]>(
    'vscode.executeDefinitionProvider',
    uri,
    position,
  );
  return {
    uri: uri.toString(),
    position: { line: position.line, character: position.character },
    definitions: (locations ?? []).map(locationToInfo),
  };
}

// ---------------------------------------------------------------------------
// symbol.references
// ---------------------------------------------------------------------------

/**
 * Find all references to a symbol at the given position in the document.
 * Uses vscode.executeReferenceProvider.
 */
export async function references(
  uri: vscode.Uri,
  position: vscode.Position,
  includeDeclaration: boolean = true,
): Promise<SymbolReferencesResult> {
  const locations = await vscode.commands.executeCommand<vscode.Location[]>(
    'vscode.executeReferenceProvider',
    uri,
    position,
    { includeDeclaration },
  );
  return {
    uri: uri.toString(),
    position: { line: position.line, character: position.character },
    references: (locations ?? []).map(locationToInfo),
  };
}

// ---------------------------------------------------------------------------
// symbol.rename
// ---------------------------------------------------------------------------

/**
 * Rename a symbol at the given position in the document.
 * Uses vscode.executeRenameProvider to get a WorkspaceEdit, then applies it.
 */
export async function rename(
  uri: vscode.Uri,
  position: vscode.Position,
  newName: string,
): Promise<SymbolRenameResult> {
  const edit = await vscode.commands.executeCommand<vscode.WorkspaceEdit>(
    'vscode.executeRenameProvider',
    uri,
    position,
    newName,
  );
  if (!edit) {
    return {
      uri: uri.toString(),
      position: { line: position.line, character: position.character },
      oldName: '',
      newName,
      changed: false,
      editCount: 0,
    };
  }
  const ok = await vscode.workspace.applyEdit(edit);
  return {
    uri: uri.toString(),
    position: { line: position.line, character: position.character },
    oldName: '',
    newName,
    changed: ok,
    editCount: edit.size,
  };
}

// ---------------------------------------------------------------------------
// workspace.symbols
// ---------------------------------------------------------------------------

/**
 * Search for symbols across the entire workspace.
 * Uses vscode.executeWorkspaceSymbolProvider.
 */
export async function workspaceSymbols(
  query: string,
): Promise<WorkspaceSymbolsResult> {
  const symbols = await vscode.commands.executeCommand<vscode.SymbolInformation[]>(
    'vscode.executeWorkspaceSymbolProvider',
    query,
  );
  return {
    query,
    symbols: (symbols ?? []).map(symbolInfoToWorkspace),
  };
}

// ---------------------------------------------------------------------------
// diagnostics.read
// ---------------------------------------------------------------------------

/**
 * Read diagnostics for a specific document.
 * Uses vscode.languages.getDiagnostics(uri).
 */
export async function readDiagnostics(
  uri: vscode.Uri,
): Promise<DiagnosticsReadResult> {
  const diagnostics = vscode.languages.getDiagnostics(uri);
  return {
    uri: uri.toString(),
    diagnostics: diagnostics.map(diagnosticToInfo),
  };
}

/**
 * Read all diagnostics across the entire workspace.
 * Uses vscode.languages.getDiagnostics() (no args = all).
 */
export async function readAllDiagnostics(): Promise<DiagnosticsReadResult> {
  const allDiagnostics = vscode.languages.getDiagnostics();
  const result: DiagnosticInfo[] = [];
  for (const [uri, diagnostics] of allDiagnostics) {
    for (const d of diagnostics) {
      result.push(diagnosticToInfo(d));
    }
  }
  return { diagnostics: result };
}

// ---------------------------------------------------------------------------
// Additional: document symbols (bonus primitive)
// ---------------------------------------------------------------------------

/**
 * Get all symbols (outline) for a document.
 * Uses vscode.executeDocumentSymbolProvider.
 */
export async function documentSymbols(
  uri: vscode.Uri,
): Promise<SymbolInfo[]> {
  const symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
    'vscode.executeDocumentSymbolProvider',
    uri,
  );
  return (symbols ?? []).map(documentSymbolToInfo);
}
