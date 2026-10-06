/**
 * VSCODER:// Bridge — Typed IDE Capabilities Surface
 *
 * Phase 2: Exposes typed capabilities for workspace, editor, symbol, refactor,
 * diagnostics, task, test, debug, terminal, scm, and ide namespaces.
 *
 * Each capability carries a defined effect class:
 *   LOCAL    – no grant needed (read-only, in-memory, ephemeral)
 *   DURABLE  – policy/confirmation required (persistent state changes)
 *   EXTERNAL – passkey + transaction-bound grant required (network, APIs)
 *
 * ide.executeCommand is the exceptional escape hatch that resolves through
 * the command resolver.
 *
 * All capabilities are registered in a capability registry.
 */

import * as vscode from 'vscode';
import { RiskLevel } from '../authority/policy';

// ---------------------------------------------------------------------------
// Core Types
// ---------------------------------------------------------------------------

/** Effect class for a capability — determines grant requirements. */
export type EffectClass = RiskLevel;

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

/** A serializable CodeAction summary. */
export interface RefactorActionSummary {
  title: string;
  kind: string;
  isPreferred: boolean;
  hasEdit: boolean;
  hasCommand: boolean;
}

/** Git status information. */
export interface GitStatusInfo {
  branch: string;
  changes: number;
  commitTemplate: string;
  rootUri: string | undefined;
}

/** Debug session inspection result. */
export interface DebugInspectionResult {
  isActive: boolean;
  sessionId?: string;
  sessionType?: string;
  sessionName?: string;
  configuration?: vscode.DebugConfiguration;
  workspaceFolder?: vscode.WorkspaceFolder;
  parentSessionId?: string;
  breakpoints: readonly vscode.Breakpoint[];
}

// ---------------------------------------------------------------------------
// Capability Definition
// ---------------------------------------------------------------------------

/** Defines a single typed capability. */
export interface CapabilityDefinition {
  /** Unique capability name, e.g. "workspace.readFile". */
  name: string;
  /** Effect class determining grant requirements. */
  effect: EffectClass;
  /** Human-readable description. */
  description: string;
  /** Parameter schema (informal). */
  params?: Record<string, string>;
  /** Return type description. */
  returns?: string;
}

// ---------------------------------------------------------------------------
// Capability Registry
// ---------------------------------------------------------------------------

/**
 * Central registry for all IDE capabilities.
 * Provides lookup, listing, and effect-class queries.
 */
export class CapabilityRegistry {
  private capabilities = new Map<string, CapabilityDefinition>();

  /** Register a capability definition. */
  register(cap: CapabilityDefinition): void {
    this.capabilities.set(cap.name, cap);
  }

  /** Register multiple capabilities at once. */
  registerAll(caps: CapabilityDefinition[]): void {
    for (const cap of caps) {
      this.register(cap);
    }
  }

  /** Look up a capability by name. Returns undefined if not found. */
  get(name: string): CapabilityDefinition | undefined {
    return this.capabilities.get(name);
  }

  /** Check if a capability is registered. */
  has(name: string): boolean {
    return this.capabilities.has(name);
  }

  /** List all registered capabilities. */
  list(): CapabilityDefinition[] {
    return Array.from(this.capabilities.values());
  }

  /** List capabilities filtered by effect class. */
  listByEffect(effect: EffectClass): CapabilityDefinition[] {
    return this.list().filter((c) => c.effect === effect);
  }

  /** List capabilities filtered by namespace prefix (e.g. "workspace"). */
  listByNamespace(namespace: string): CapabilityDefinition[] {
    const prefix = namespace + '.';
    return this.list().filter((c) => c.name.startsWith(prefix));
  }

  /** Get the total number of registered capabilities. */
  get size(): number {
    return this.capabilities.size;
  }
}

// ---------------------------------------------------------------------------
// Command Resolver
// ---------------------------------------------------------------------------

/**
 * Resolves ide.executeCommand calls through VS Code's command system.
 * This is the exceptional escape hatch for capabilities that don't have
 * a dedicated typed wrapper.
 */
export class CommandResolver {
  /**
   * Execute a VS Code command by ID with optional arguments.
   * @param commandId - The command identifier (e.g. "editor.action.formatDocument").
   * @param args - Arguments to pass to the command.
   * @returns The command's return value.
   */
  async resolve(commandId: string, ...args: unknown[]): Promise<unknown> {
    return vscode.commands.executeCommand(commandId, ...args);
  }

  /**
   * Check if a command is registered in VS Code.
   * @param commandId - The command identifier.
   * @returns Whether the command exists.
   */
  async hasCommand(commandId: string): Promise<boolean> {
    const commands = await vscode.commands.getCommands();
    return commands.includes(commandId);
  }
}

// ---------------------------------------------------------------------------
// Capability Definitions — Workspace
// ---------------------------------------------------------------------------

const workspaceCapabilities: CapabilityDefinition[] = [
  { name: 'workspace.readFile', effect: 'LOCAL', description: 'Read file contents from disk', params: { path: 'string' }, returns: 'string' },
  { name: 'workspace.writeFile', effect: 'DURABLE', description: 'Write content to a file on disk', params: { path: 'string', content: 'string' }, returns: 'void' },
  { name: 'workspace.listFiles', effect: 'LOCAL', description: 'List files in a directory', params: { path: 'string' }, returns: 'string[]' },
  { name: 'workspace.createDirectory', effect: 'DURABLE', description: 'Create a directory on disk', params: { path: 'string' }, returns: 'void' },
  { name: 'workspace.deleteFile', effect: 'DURABLE', description: 'Delete a file from disk', params: { path: 'string' }, returns: 'void' },
  { name: 'workspace.findFiles', effect: 'LOCAL', description: 'Find files matching a glob pattern', params: { pattern: 'string' }, returns: 'Uri[]' },
  { name: 'workspace.getWorkspaceFolders', effect: 'LOCAL', description: 'Get all workspace folders', returns: 'WorkspaceFolder[]' },
  { name: 'workspace.asRelativePath', effect: 'LOCAL', description: 'Convert absolute path to workspace-relative path', params: { path: 'string' }, returns: 'string' },
  { name: 'workspace.openTextDocument', effect: 'LOCAL', description: 'Open a text document without revealing it', params: { path: 'string' }, returns: 'Thenable<TextDocument>' },
  { name: 'workspace.saveAll', effect: 'DURABLE', description: 'Save all dirty documents', returns: 'Thenable<boolean>' },
  { name: 'workspace.applyEdit', effect: 'DURABLE', description: 'Apply a workspace edit (batch changes)', params: { edit: 'WorkspaceEdit' }, returns: 'Thenable<boolean>' },
  { name: 'workspace.getConfiguration', effect: 'LOCAL', description: 'Get a configuration value', params: { section: 'string' }, returns: 'T' },
  { name: 'workspace.updateConfiguration', effect: 'DURABLE', description: 'Update a configuration value', params: { section: 'string', value: 'unknown' }, returns: 'Thenable<void>' },
  { name: 'workspace.registerTextDocumentContentProvider', effect: 'DURABLE', description: 'Register a content provider for a URI scheme', params: { scheme: 'string', provider: 'TextDocumentContentProvider' }, returns: 'Disposable' },
  { name: 'workspace.onDidSaveTextDocument', effect: 'LOCAL', description: 'Event fired when a text document is saved', returns: 'Event<TextDocument>' },
  { name: 'workspace.onDidOpenTextDocument', effect: 'LOCAL', description: 'Event fired when a text document is opened', returns: 'Event<TextDocument>' },
  { name: 'workspace.onDidCloseTextDocument', effect: 'LOCAL', description: 'Event fired when a text document is closed', returns: 'Event<TextDocument>' },
  { name: 'workspace.onDidChangeTextDocument', effect: 'LOCAL', description: 'Event fired when a text document changes', returns: 'Event<TextDocumentChangeEvent>' },
  { name: 'workspace.onDidChangeConfiguration', effect: 'LOCAL', description: 'Event fired when configuration changes', returns: 'Event<ConfigurationChangeEvent>' },
];

// ---------------------------------------------------------------------------
// Capability Definitions — Editor
// ---------------------------------------------------------------------------

const editorCapabilities: CapabilityDefinition[] = [
  { name: 'editor.openDocument', effect: 'LOCAL', description: 'Open and reveal a text document', params: { path: 'string' }, returns: 'Thenable<TextEditor>' },
  { name: 'editor.closeDocument', effect: 'DURABLE', description: 'Close an open editor for a document', params: { uri: 'Uri' }, returns: 'Thenable<boolean>' },
  { name: 'editor.saveDocument', effect: 'DURABLE', description: 'Save a document', params: { uri: 'Uri' }, returns: 'Thenable<boolean>' },
  { name: 'editor.getActiveEditor', effect: 'LOCAL', description: 'Get the currently active text editor', returns: 'TextEditor | undefined' },
  { name: 'editor.getVisibleEditors', effect: 'LOCAL', description: 'Get all visible text editors', returns: 'TextEditor[]' },
  { name: 'editor.showTextDocument', effect: 'LOCAL', description: 'Show a text document in an editor', params: { uri: 'Uri', options: 'TextDocumentShowOptions' }, returns: 'Thenable<TextEditor>' },
  { name: 'editor.editDocument', effect: 'DURABLE', description: 'Apply edits to a document', params: { uri: 'Uri', edits: 'TextEdit[]' }, returns: 'Thenable<boolean>' },
  { name: 'editor.insertSnippet', effect: 'DURABLE', description: 'Insert a snippet at the cursor', params: { snippet: 'SnippetString', location: 'Position | Range' }, returns: 'Thenable<boolean>' },
  { name: 'editor.setDecorations', effect: 'LOCAL', description: 'Set decorations on an editor', params: { editor: 'TextEditor', decorationType: 'TextEditorDecorationType', ranges: 'Range[]' }, returns: 'void' },
  { name: 'editor.revealRange', effect: 'LOCAL', description: 'Reveal a range in an editor', params: { range: 'Range', revealType: 'TextEditorRevealType' }, returns: 'void' },
  { name: 'editor.getSelection', effect: 'LOCAL', description: 'Get the current selection', returns: 'Selection | undefined' },
  { name: 'editor.setSelection', effect: 'LOCAL', description: 'Set the current selection', params: { selection: 'Selection' }, returns: 'void' },
  { name: 'editor.getCursorPosition', effect: 'LOCAL', description: 'Get the cursor position', returns: 'Position | undefined' },
  { name: 'editor.setCursorPosition', effect: 'LOCAL', description: 'Set the cursor position', params: { position: 'Position' }, returns: 'void' },
  { name: 'editor.getVisibleRanges', effect: 'LOCAL', description: 'Get visible ranges in an editor', returns: 'Range[]' },
  { name: 'editor.getDocument', effect: 'LOCAL', description: 'Get the document from an editor', params: { editor: 'TextEditor' }, returns: 'TextDocument' },
  { name: 'editor.getLanguageId', effect: 'LOCAL', description: 'Get the language ID of a document', params: { uri: 'Uri' }, returns: 'string' },
  { name: 'editor.executeFormatDocument', effect: 'DURABLE', description: 'Format the entire document', params: { uri: 'Uri' }, returns: 'Thenable<TextEdit[]>' },
  { name: 'editor.executeFormatSelection', effect: 'DURABLE', description: 'Format the current selection', params: { uri: 'Uri', range: 'Range' }, returns: 'Thenable<TextEdit[]>' },
  { name: 'editor.executeRename', effect: 'DURABLE', description: 'Rename the symbol at the cursor', params: { uri: 'Uri', position: 'Position', newName: 'string' }, returns: 'Thenable<WorkspaceEdit | undefined>' },
  { name: 'editor.executeDefinitionProvider', effect: 'LOCAL', description: 'Find the definition of the symbol at the cursor', params: { uri: 'Uri', position: 'Position' }, returns: 'Thenable<Definition | undefined>' },
  { name: 'editor.executeTypeDefinitionProvider', effect: 'LOCAL', description: 'Find the type definition of the symbol at the cursor', params: { uri: 'Uri', position: 'Position' }, returns: 'Thenable<Definition | undefined>' },
  { name: 'editor.executeImplementationProvider', effect: 'LOCAL', description: 'Find implementations of the symbol at the cursor', params: { uri: 'Uri', position: 'Position' }, returns: 'Thenable<Definition | undefined>' },
  { name: 'editor.executeHoverProvider', effect: 'LOCAL', description: 'Get hover information at the cursor', params: { uri: 'Uri', position: 'Position' }, returns: 'Thenable<Hover | undefined>' },
  { name: 'editor.executeDocumentSymbolProvider', effect: 'LOCAL', description: 'Get all symbols in a document', params: { uri: 'Uri' }, returns: 'Thenable<SymbolInformation[]>' },
  { name: 'editor.executeCodeActionProvider', effect: 'LOCAL', description: 'Get code actions for a range', params: { uri: 'Uri', range: 'Range', kind: 'CodeActionKind' }, returns: 'Thenable<CodeAction[]>' },
  { name: 'editor.executeCompletionItemProvider', effect: 'LOCAL', description: 'Get completion items at the cursor', params: { uri: 'Uri', position: 'Position' }, returns: 'Thenable<CompletionList | undefined>' },
  { name: 'editor.executeSignatureHelpProvider', effect: 'LOCAL', description: 'Get signature help at the cursor', params: { uri: 'Uri', position: 'Position' }, returns: 'Thenable<SignatureHelp | undefined>' },
  { name: 'editor.executeLinkProvider', effect: 'LOCAL', description: 'Get links in a document', params: { uri: 'Uri' }, returns: 'Thenable<DocumentLink[]>' },
  { name: 'editor.executeColorProvider', effect: 'LOCAL', description: 'Get color information in a document', params: { uri: 'Uri' }, returns: 'Thenable<ColorInformation[]>' },
  { name: 'editor.executeFoldingRangeProvider', effect: 'LOCAL', description: 'Get folding ranges in a document', params: { uri: 'Uri' }, returns: 'Thenable<FoldingRange[]>' },
  { name: 'editor.executeSelectionRangeProvider', effect: 'LOCAL', description: 'Get selection ranges in a document', params: { uri: 'Uri', positions: 'Position[]' }, returns: 'Thenable<SelectionRange[]>' },
  { name: 'editor.executeCallHierarchyProvider', effect: 'LOCAL', description: 'Get call hierarchy items at the cursor', params: { uri: 'Uri', position: 'Position' }, returns: 'Thenable<CallHierarchyItem[]>' },
  { name: 'editor.executeDocumentHighlightProvider', effect: 'LOCAL', description: 'Get document highlights at the cursor', params: { uri: 'Uri', position: 'Position' }, returns: 'Thenable<DocumentHighlight[]>' },
  { name: 'editor.executeReferenceProvider', effect: 'LOCAL', description: 'Find references to the symbol at the cursor', params: { uri: 'Uri', position: 'Position' }, returns: 'Thenable<Location[]>' },
  { name: 'editor.executeCodeLensProvider', effect: 'LOCAL', description: 'Get code lenses in a document', params: { uri: 'Uri' }, returns: 'Thenable<CodeLens[]>' },
  { name: 'editor.executeInlineValueProvider', effect: 'LOCAL', description: 'Get inline values in a document', params: { uri: 'Uri', range: 'Range' }, returns: 'Thenable<InlineValue[]>' },
  { name: 'editor.executeInlayHintProvider', effect: 'LOCAL', description: 'Get inlay hints in a document', params: { uri: 'Uri', range: 'Range' }, returns: 'Thenable<InlayHint[]>' },
];

// ---------------------------------------------------------------------------
// Capability Definitions — Symbol
// ---------------------------------------------------------------------------

const symbolCapabilities: CapabilityDefinition[] = [
  { name: 'symbol.find', effect: 'LOCAL', description: 'Find definition of a symbol at a position', params: { uri: 'Uri', position: 'Position' }, returns: 'SymbolFindResult' },
  { name: 'symbol.references', effect: 'LOCAL', description: 'Find all references to a symbol', params: { uri: 'Uri', position: 'Position' }, returns: 'SymbolReferencesResult' },
  { name: 'symbol.rename', effect: 'DURABLE', description: 'Rename a symbol across the workspace', params: { uri: 'Uri', position: 'Position', newName: 'string' }, returns: 'SymbolRenameResult' },
  { name: 'symbol.workspaceSymbols', effect: 'LOCAL', description: 'Search symbols across the entire workspace', params: { query: 'string' }, returns: 'WorkspaceSymbolsResult' },
  { name: 'symbol.definition', effect: 'LOCAL', description: 'Get the definition of a symbol', params: { uri: 'Uri', position: 'Position' }, returns: 'LocationInfo[]' },
  { name: 'symbol.typeDefinition', effect: 'LOCAL', description: 'Get the type definition of a symbol', params: { uri: 'Uri', position: 'Position' }, returns: 'LocationInfo[]' },
  { name: 'symbol.implementation', effect: 'LOCAL', description: 'Get implementations of a symbol', params: { uri: 'Uri', position: 'Position' }, returns: 'LocationInfo[]' },
  { name: 'symbol.hover', effect: 'LOCAL', description: 'Get hover information for a symbol', params: { uri: 'Uri', position: 'Position' }, returns: 'Hover | undefined' },
  { name: 'symbol.documentSymbols', effect: 'LOCAL', description: 'Get all symbols in a document', params: { uri: 'Uri' }, returns: 'SymbolInfo[]' },
  { name: 'symbol.documentHighlights', effect: 'LOCAL', description: 'Get document highlights at a position', params: { uri: 'Uri', position: 'Position' }, returns: 'DocumentHighlight[]' },
  { name: 'symbol.callHierarchyIncoming', effect: 'LOCAL', description: 'Get incoming calls for a symbol', params: { uri: 'Uri', position: 'Position' }, returns: 'CallHierarchyIncomingCall[]' },
  { name: 'symbol.callHierarchyOutgoing', effect: 'LOCAL', description: 'Get outgoing calls for a symbol', params: { uri: 'Uri', position: 'Position' }, returns: 'CallHierarchyOutgoingCall[]' },
];

// ---------------------------------------------------------------------------
// Capability Definitions — Refactor
// ---------------------------------------------------------------------------

const refactorCapabilities: CapabilityDefinition[] = [
  { name: 'refactor.list', effect: 'LOCAL', description: 'Enumerate available code actions for a range', params: { uri: 'Uri', range: 'Range' }, returns: 'RefactorListResult' },
  { name: 'refactor.apply', effect: 'DURABLE', description: 'Apply a specific code action by title', params: { uri: 'Uri', actionTitle: 'string' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.extractMethod', effect: 'DURABLE', description: 'Extract selected code into a new method', params: { uri: 'Uri', range: 'Range', methodName: 'string' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.extractFunction', effect: 'DURABLE', description: 'Extract selected code into a new function', params: { uri: 'Uri', range: 'Range', functionName: 'string' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.extractVariable', effect: 'DURABLE', description: 'Extract an expression into a variable', params: { uri: 'Uri', range: 'Range', variableName: 'string' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.extractConstant', effect: 'DURABLE', description: 'Extract an expression into a constant', params: { uri: 'Uri', range: 'Range', constantName: 'string' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.moveToNewFile', effect: 'DURABLE', description: 'Move a symbol to a new file', params: { uri: 'Uri', position: 'Position', newFilePath: 'string' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.moveToClass', effect: 'DURABLE', description: 'Move a symbol to a different class', params: { uri: 'Uri', position: 'Position', targetClass: 'string' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.rewriteFunctionToClass', effect: 'DURABLE', description: 'Convert a function to a class', params: { uri: 'Uri', position: 'Position', className: 'string' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.rewriteAddParameter', effect: 'DURABLE', description: 'Add a parameter to a function', params: { uri: 'Uri', position: 'Position', paramName: 'string', paramType: 'string' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.rewriteRemoveParameter', effect: 'DURABLE', description: 'Remove a parameter from a function', params: { uri: 'Uri', position: 'Position', paramName: 'string' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.organizeImports', effect: 'DURABLE', description: 'Organize imports (sort, remove unused)', params: { uri: 'Uri' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.inlineVariable', effect: 'DURABLE', description: 'Inline a variable at all usage sites', params: { uri: 'Uri', position: 'Position' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.convertToAsync', effect: 'DURABLE', description: 'Convert a function to async', params: { uri: 'Uri', position: 'Position' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.convertToArrow', effect: 'DURABLE', description: 'Convert a function to an arrow function', params: { uri: 'Uri', position: 'Position' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.convertToTemplateLiteral', effect: 'DURABLE', description: 'Convert string concatenation to template literal', params: { uri: 'Uri', range: 'Range' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.addJSDoc', effect: 'DURABLE', description: 'Add JSDoc comments to a function', params: { uri: 'Uri', position: 'Position' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.removeUnused', effect: 'DURABLE', description: 'Remove unused code (variables, imports, functions)', params: { uri: 'Uri' }, returns: 'RefactorApplyResult' },
  { name: 'refactor.sortMembers', effect: 'DURABLE', description: 'Sort class/object members alphabetically', params: { uri: 'Uri', position: 'Position' }, returns: 'RefactorApplyResult' },
];

// ---------------------------------------------------------------------------
// Capability Definitions — Diagnostics
// ---------------------------------------------------------------------------

const diagnosticsCapabilities: CapabilityDefinition[] = [
  { name: 'diagnostics.read', effect: 'LOCAL', description: 'Read diagnostics for a document or workspace', params: { uri: 'Uri' }, returns: 'DiagnosticsReadResult' },
  { name: 'diagnostics.getForUri', effect: 'LOCAL', description: 'Get diagnostics for a specific URI', params: { uri: 'Uri' }, returns: 'Diagnostic[]' },
  { name: 'diagnostics.getForEditor', effect: 'LOCAL', description: 'Get diagnostics for the active editor', returns: 'Diagnostic[]' },
  { name: 'diagnostics.clear', effect: 'DURABLE', description: 'Clear diagnostics for a URI or all', params: { uri: 'Uri' }, returns: 'void' },
  { name: 'diagnostics.getSeverityCount', effect: 'LOCAL', description: 'Get count of diagnostics by severity', params: { uri: 'Uri' }, returns: 'Record<DiagnosticSeverity, number>' },
  { name: 'diagnostics.getErrors', effect: 'LOCAL', description: 'Get only error-level diagnostics', params: { uri: 'Uri' }, returns: 'Diagnostic[]' },
  { name: 'diagnostics.getWarnings', effect: 'LOCAL', description: 'Get only warning-level diagnostics', params: { uri: 'Uri' }, returns: 'Diagnostic[]' },
  { name: 'diagnostics.getHints', effect: 'LOCAL', description: 'Get only hint-level diagnostics', params: { uri: 'Uri' }, returns: 'Diagnostic[]' },
  { name: 'diagnostics.getInformation', effect: 'LOCAL', description: 'Get only info-level diagnostics', params: { uri: 'Uri' }, returns: 'Diagnostic[]' },
  { name: 'diagnostics.onDidChangeDiagnostics', effect: 'LOCAL', description: 'Event fired when diagnostics change', returns: 'Event<DiagnosticChangeEvent>' },
];

// ---------------------------------------------------------------------------
// Capability Definitions — Task
// ---------------------------------------------------------------------------

const taskCapabilities: CapabilityDefinition[] = [
  { name: 'task.run', effect: 'DURABLE', description: 'Run a task by name or Task object', params: { taskName: 'string' }, returns: 'Thenable<TaskExecution>' },
  { name: 'task.fetch', effect: 'LOCAL', description: 'Fetch all available tasks', params: { type: 'string' }, returns: 'Thenable<Task[]>' },
  { name: 'task.getDefaultBuildTask', effect: 'LOCAL', description: 'Get the default build task', returns: 'Thenable<Task | undefined>' },
  { name: 'task.getDefaultTestTask', effect: 'LOCAL', description: 'Get the default test task', returns: 'Thenable<Task | undefined>' },
  { name: 'task.terminate', effect: 'DURABLE', description: 'Terminate a running task', params: { execution: 'TaskExecution' }, returns: 'Thenable<void>' },
  { name: 'task.restart', effect: 'DURABLE', description: 'Restart a task', params: { execution: 'TaskExecution' }, returns: 'Thenable<TaskExecution>' },
  { name: 'task.getActiveTasks', effect: 'LOCAL', description: 'Get all currently running tasks', returns: 'TaskExecution[]' },
  { name: 'task.registerTaskProvider', effect: 'DURABLE', description: 'Register a task provider for a task type', params: { type: 'string', provider: 'TaskProvider' }, returns: 'Disposable' },
  { name: 'task.onDidStartTask', effect: 'LOCAL', description: 'Event fired when a task starts', returns: 'Event<TaskStartEvent>' },
  { name: 'task.onDidEndTask', effect: 'LOCAL', description: 'Event fired when a task ends', returns: 'Event<TaskEndEvent>' },
  { name: 'task.onDidStartTaskProcess', effect: 'LOCAL', description: 'Event fired when a task process starts', returns: 'Event<TaskProcessStartEvent>' },
  { name: 'task.onDidEndTaskProcess', effect: 'LOCAL', description: 'Event fired when a task process ends', returns: 'Event<TaskProcessEndEvent>' },
];

// ---------------------------------------------------------------------------
// Capability Definitions — Test
// ---------------------------------------------------------------------------

const testCapabilities: CapabilityDefinition[] = [
  { name: 'test.run', effect: 'DURABLE', description: 'Run all tests or a test controller\'s tests', params: { controllerId: 'string', testItemIds: 'string[]', debug: 'boolean', coverage: 'boolean' }, returns: 'Thenable<void>' },
  { name: 'test.target', effect: 'DURABLE', description: 'Run a specific test target by ID', params: { testItemId: 'string', controllerId: 'string', debug: 'boolean' }, returns: 'Thenable<void>' },
  { name: 'test.coverage', effect: 'DURABLE', description: 'Run tests with coverage', params: { controllerId: 'string', testItemIds: 'string[]' }, returns: 'Thenable<void>' },
  { name: 'test.createController', effect: 'DURABLE', description: 'Create a test controller', params: { controllerId: 'string', label: 'string' }, returns: 'TestController' },
  { name: 'test.getControllers', effect: 'LOCAL', description: 'Get all registered test controllers', returns: 'TestController[]' },
  { name: 'test.getController', effect: 'LOCAL', description: 'Get a test controller by ID', params: { controllerId: 'string' }, returns: 'TestController | undefined' },
  { name: 'test.getTestItem', effect: 'LOCAL', description: 'Get a test item by ID from a controller', params: { controllerId: 'string', testItemId: 'string' }, returns: 'TestItem | undefined' },
  { name: 'test.getTestItems', effect: 'LOCAL', description: 'Get all test items from a controller', params: { controllerId: 'string' }, returns: 'TestItem[]' },
  { name: 'test.createRunProfile', effect: 'DURABLE', description: 'Create a test run profile', params: { controllerId: 'string', label: 'string', kind: 'TestRunProfileKind' }, returns: 'TestRunProfile' },
  { name: 'test.refreshTests', effect: 'LOCAL', description: 'Refresh tests in a controller', params: { controllerId: 'string' }, returns: 'Thenable<void>' },
  { name: 'test.runTestsFromProfile', effect: 'DURABLE', description: 'Run tests from a profile', params: { profile: 'TestRunProfile', request: 'TestRunRequest' }, returns: 'Thenable<void>' },
  { name: 'test.onDidChangeTestResults', effect: 'LOCAL', description: 'Event fired when test results change', returns: 'Event<TestRunResult>' },
  { name: 'test.onDidStartTestRun', effect: 'LOCAL', description: 'Event fired when a test run starts', returns: 'Event<TestRun>' },
  { name: 'test.onDidEndTestRun', effect: 'LOCAL', description: 'Event fired when a test run ends', returns: 'Event<TestRun>' },
];

// ---------------------------------------------------------------------------
// Capability Definitions — Debug
// ---------------------------------------------------------------------------

const debugCapabilities: CapabilityDefinition[] = [
  { name: 'debug.start', effect: 'DURABLE', description: 'Start a debug session', params: { nameOrConfiguration: 'string | DebugConfiguration', folder: 'WorkspaceFolder' }, returns: 'Thenable<boolean>' },
  { name: 'debug.stop', effect: 'DURABLE', description: 'Stop the active debug session', params: { sessionId: 'string' }, returns: 'Thenable<void>' },
  { name: 'debug.inspect', effect: 'LOCAL', description: 'Inspect the current debug session', returns: 'DebugInspectionResult' },
  { name: 'debug.addBreakpoint', effect: 'DURABLE', description: 'Add a breakpoint', params: { breakpoint: 'Breakpoint' }, returns: 'void' },
  { name: 'debug.removeBreakpoint', effect: 'DURABLE', description: 'Remove a breakpoint', params: { breakpoint: 'Breakpoint' }, returns: 'void' },
  { name: 'debug.getBreakpoints', effect: 'LOCAL', description: 'Get all breakpoints', returns: 'Breakpoint[]' },
  { name: 'debug.clearBreakpoints', effect: 'DURABLE', description: 'Remove all breakpoints', returns: 'void' },
  { name: 'debug.continue', effect: 'DURABLE', description: 'Continue execution in the debug session', params: { sessionId: 'string' }, returns: 'Thenable<void>' },
  { name: 'debug.stepInto', effect: 'DURABLE', description: 'Step into the next statement', params: { sessionId: 'string' }, returns: 'Thenable<void>' },
  { name: 'debug.stepOver', effect: 'DURABLE', description: 'Step over the next statement', params: { sessionId: 'string' }, returns: 'Thenable<void>' },
  { name: 'debug.stepOut', effect: 'DURABLE', description: 'Step out of the current function', params: { sessionId: 'string' }, returns: 'Thenable<void>' },
  { name: 'debug.evaluate', effect: 'LOCAL', description: 'Evaluate an expression in the debug session context', params: { expression: 'string', frameId: 'number', context: 'string' }, returns: 'Thenable<DebugProtocol.EvaluateResponse>' },
  { name: 'debug.getStackFrames', effect: 'LOCAL', description: 'Get stack frames from the debug session', params: { sessionId: 'string' }, returns: 'DebugProtocol.StackFrame[]' },
  { name: 'debug.getScopes', effect: 'LOCAL', description: 'Get scopes for a stack frame', params: { frameId: 'number' }, returns: 'DebugProtocol.Scope[]' },
  { name: 'debug.getVariables', effect: 'LOCAL', description: 'Get variables for a scope', params: { variablesReference: 'number' }, returns: 'DebugProtocol.Variable[]' },
  { name: 'debug.registerDebugConfigurationProvider', effect: 'DURABLE', description: 'Register a debug configuration provider', params: { type: 'string', provider: 'DebugConfigurationProvider' }, returns: 'Disposable' },
  { name: 'debug.onDidStartDebugSession', effect: 'LOCAL', description: 'Event fired when a debug session starts', returns: 'Event<DebugSession>' },
  { name: 'debug.onDidEndDebugSession', effect: 'LOCAL', description: 'Event fired when a debug session ends', returns: 'Event<DebugSession>' },
  { name: 'debug.onDidChangeActiveDebugSession', effect: 'LOCAL', description: 'Event fired when the active debug session changes', returns: 'Event<DebugSession | undefined>' },
  { name: 'debug.onDidReceiveDebugSessionCustomEvent', effect: 'LOCAL', description: 'Event fired when a debug session receives a custom event', returns: 'Event<DebugSessionCustomEvent>' },
  { name: 'debug.onDidChangeBreakpoints', effect: 'LOCAL', description: 'Event fired when breakpoints change', returns: 'Event<BreakpointsChangeEvent>' },
];

// ---------------------------------------------------------------------------
// Capability Definitions — Terminal
// ---------------------------------------------------------------------------

const terminalCapabilities: CapabilityDefinition[] = [
  { name: 'terminal.run', effect: 'DURABLE', description: 'Run a shell command in a terminal', params: { command: 'string', name: 'string', cwd: 'string' }, returns: 'Terminal' },
  { name: 'terminal.create', effect: 'DURABLE', description: 'Create a new terminal', params: { name: 'string', cwd: 'string', env: 'Record<string, string>' }, returns: 'Terminal' },
  { name: 'terminal.sendText', effect: 'DURABLE', description: 'Send text to a terminal', params: { terminal: 'Terminal', text: 'string', addNewLine: 'boolean' }, returns: 'void' },
  { name: 'terminal.show', effect: 'LOCAL', description: 'Show a terminal', params: { terminal: 'Terminal', preserveFocus: 'boolean' }, returns: 'void' },
  { name: 'terminal.hide', effect: 'LOCAL', description: 'Hide a terminal', params: { terminal: 'Terminal' }, returns: 'void' },
  { name: 'terminal.dispose', effect: 'DURABLE', description: 'Dispose a terminal', params: { terminal: 'Terminal' }, returns: 'void' },
  { name: 'terminal.getActive', effect: 'LOCAL', description: 'Get the active terminal', returns: 'Terminal | undefined' },
  { name: 'terminal.getAll', effect: 'LOCAL', description: 'Get all terminals', returns: 'Terminal[]' },
  { name: 'terminal.getByName', effect: 'LOCAL', description: 'Get a terminal by name', params: { name: 'string' }, returns: 'Terminal | undefined' },
  { name: 'terminal.registerTerminalProfileProvider', effect: 'DURABLE', description: 'Register a terminal profile provider', params: { extensionId: 'string', provider: 'TerminalProfileProvider' }, returns: 'Disposable' },
  { name: 'terminal.registerTerminalLinkProvider', effect: 'DURABLE', description: 'Register a terminal link provider', params: { provider: 'TerminalLinkProvider' }, returns: 'Disposable' },
  { name: 'terminal.onDidOpenTerminal', effect: 'LOCAL', description: 'Event fired when a terminal is opened', returns: 'Event<Terminal>' },
  { name: 'terminal.onDidCloseTerminal', effect: 'LOCAL', description: 'Event fired when a terminal is closed', returns: 'Event<Terminal>' },
  { name: 'terminal.onDidChangeTerminalState', effect: 'LOCAL', description: 'Event fired when terminal state changes', returns: 'Event<Terminal>' },
];

// ---------------------------------------------------------------------------
// Capability Definitions — SCM (Source Control Management)
// ---------------------------------------------------------------------------

const scmCapabilities: CapabilityDefinition[] = [
  { name: 'scm.status', effect: 'LOCAL', description: 'Get git status information', returns: 'GitStatusInfo' },
  { name: 'scm.diff', effect: 'LOCAL', description: 'Show git diff', returns: 'Thenable<void>' },
  { name: 'scm.branch', effect: 'LOCAL', description: 'Show/create branches', returns: 'Thenable<void>' },
  { name: 'scm.commit', effect: 'DURABLE', description: 'Commit changes', params: { message: 'string' }, returns: 'Thenable<void>' },
  { name: 'scm.push', effect: 'EXTERNAL', description: 'Push to remote', returns: 'Thenable<void>' },
  { name: 'scm.pull', effect: 'EXTERNAL', description: 'Pull from remote', returns: 'Thenable<void>' },
  { name: 'scm.fetch', effect: 'EXTERNAL', description: 'Fetch from remote', returns: 'Thenable<void>' },
  { name: 'scm.stage', effect: 'DURABLE', description: 'Stage changes', params: { uri: 'Uri' }, returns: 'Thenable<void>' },
  { name: 'scm.unstage', effect: 'DURABLE', description: 'Unstage changes', params: { uri: 'Uri' }, returns: 'Thenable<void>' },
  { name: 'scm.discard', effect: 'DURABLE', description: 'Discard changes', params: { uri: 'Uri' }, returns: 'Thenable<void>' },
  { name: 'scm.createBranch', effect: 'DURABLE', description: 'Create a new branch', params: { name: 'string', checkout: 'boolean' }, returns: 'Thenable<void>' },
  { name: 'scm.checkout', effect: 'DURABLE', description: 'Checkout a branch', params: { name: 'string' }, returns: 'Thenable<void>' },
  { name: 'scm.merge', effect: 'DURABLE', description: 'Merge a branch into the current branch', params: { name: 'string' }, returns: 'Thenable<void>' },
  { name: 'scm.rebase', effect: 'DURABLE', description: 'Rebase the current branch', params: { onto: 'string' }, returns: 'Thenable<void>' },
  { name: 'scm.reset', effect: 'DURABLE', description: 'Reset the current branch', params: { mode: 'soft | mixed | hard' }, returns: 'Thenable<void>' },
  { name: 'scm.createPatch', effect: 'LOCAL', description: 'Create a patch from changes', params: { uris: 'Uri[]' }, returns: 'string' },
  { name: 'scm.applyPatch', effect: 'DURABLE', description: 'Apply a patch', params: { patch: 'string' }, returns: 'Thenable<void>' },
  { name: 'scm.getInputBoxValue', effect: 'LOCAL', description: 'Get the current SCM input box value', returns: 'string' },
  { name: 'scm.setInputBoxValue', effect: 'DURABLE', description: 'Set the SCM input box value', params: { value: 'string' }, returns: 'void' },
  { name: 'scm.getSourceControl', effect: 'LOCAL', description: 'Get a source control by ID', params: { id: 'string' }, returns: 'SourceControl | undefined' },
  { name: 'scm.getSourceControls', effect: 'LOCAL', description: 'Get all source controls', returns: 'SourceControl[]' },
  { name: 'scm.createSourceControl', effect: 'DURABLE', description: 'Create a new source control', params: { id: 'string', label: 'string', rootUri: 'Uri' }, returns: 'SourceControl' },
  { name: 'scm.onDidChangeSourceControl', effect: 'LOCAL', description: 'Event fired when source control changes', returns: 'Event<SourceControl>' },
];

// ---------------------------------------------------------------------------
// Capability Definitions — IDE
// ---------------------------------------------------------------------------

const ideCapabilities: CapabilityDefinition[] = [
  { name: 'ide.executeCommand', effect: 'EXTERNAL', description: 'Execute a VS Code command by ID (escape hatch)', params: { commandId: 'string', args: 'unknown[]' }, returns: 'Thenable<unknown>' },
  { name: 'ide.getConfiguration', effect: 'LOCAL', description: 'Get a configuration value', params: { section: 'string' }, returns: 'T' },
  { name: 'ide.setConfiguration', effect: 'DURABLE', description: 'Update a configuration value', params: { section: 'string', value: 'unknown' }, returns: 'Thenable<void>' },
  { name: 'ide.showInformationMessage', effect: 'LOCAL', description: 'Show an information message', params: { message: 'string', items: 'string[]' }, returns: 'Thenable<string | undefined>' },
  { name: 'ide.showWarningMessage', effect: 'LOCAL', description: 'Show a warning message', params: { message: 'string', items: 'string[]' }, returns: 'Thenable<string | undefined>' },
  { name: 'ide.showErrorMessage', effect: 'LOCAL', description: 'Show an error message', params: { message: 'string', items: 'string[]' }, returns: 'Thenable<string | undefined>' },
  { name: 'ide.showQuickPick', effect: 'LOCAL', description: 'Show a quick pick menu', params: { items: 'string[]', options: 'QuickPickOptions' }, returns: 'Thenable<string | undefined>' },
  { name: 'ide.showInputBox', effect: 'LOCAL', description: 'Show an input box', params: { options: 'InputBoxOptions' }, returns: 'Thenable<string | undefined>' },
  { name: 'ide.createOutputChannel', effect: 'DURABLE', description: 'Create an output channel', params: { name: 'string' }, returns: 'OutputChannel' },
  { name: 'ide.registerCommand', effect: 'DURABLE', description: 'Register a command', params: { commandId: 'string', callback: '(...args: unknown[]) => unknown' }, returns: 'Disposable' },
  { name: 'ide.registerTextEditorCommand', effect: 'DURABLE', description: 'Register a text editor command', params: { commandId: 'string', callback: '(...args: unknown[]) => unknown' }, returns: 'Disposable' },
  { name: 'ide.getCommands', effect: 'LOCAL', description: 'Get all registered command IDs', returns: 'Thenable<string[]>' },
  { name: 'ide.hasCommand', effect: 'LOCAL', description: 'Check if a command is registered', params: { commandId: 'string' }, returns: 'Thenable<boolean>' },
  { name: 'ide.createStatusBarItem', effect: 'DURABLE', description: 'Create a status bar item', params: { alignment: 'StatusBarAlignment', priority: 'number' }, returns: 'StatusBarItem' },
  { name: 'ide.createTreeView', effect: 'DURABLE', description: 'Create a tree view', params: { viewId: 'string', options: 'TreeViewOptions' }, returns: 'TreeView' },
  { name: 'ide.createWebviewPanel', effect: 'DURABLE', description: 'Create a webview panel', params: { viewType: 'string', title: 'string', options: 'WebviewPanelOptions' }, returns: 'WebviewPanel' },
  { name: 'ide.createTerminal', effect: 'DURABLE', description: 'Create a terminal', params: { options: 'TerminalOptions' }, returns: 'Terminal' },
  { name: 'ide.createQuickPick', effect: 'DURABLE', description: 'Create a quick pick', params: { options: 'QuickPickOptions' }, returns: 'QuickPick' },
  { name: 'ide.createInputBox', effect: 'DURABLE', description: 'Create an input box', params: { options: 'InputBoxOptions' }, returns: 'InputBox' },
  { name: 'ide.createLanguageStatusItem', effect: 'DURABLE', description: 'Create a language status item', params: { id: 'string', selector: 'DocumentSelector' }, returns: 'LanguageStatusItem' },
  { name: 'ide.createDiagnosticCollection', effect: 'DURABLE', description: 'Create a diagnostic collection', params: { name: 'string' }, returns: 'DiagnosticCollection' },
  { name: 'ide.createDecorationType', effect: 'DURABLE', description: 'Create a decoration type', params: { options: 'DecorationRenderOptions' }, returns: 'TextEditorDecorationType' },
  { name: 'ide.createFileDecorationProvider', effect: 'DURABLE', description: 'Create a file decoration provider', params: { provider: 'FileDecorationProvider' }, returns: 'Disposable' },
  { name: 'ide.createDocumentLinkProvider', effect: 'DURABLE', description: 'Create a document link provider', params: { provider: 'DocumentLinkProvider' }, returns: 'Disposable' },
  { name: 'ide.createCodeActionProvider', effect: 'DURABLE', description: 'Create a code action provider', params: { provider: 'CodeActionProvider' }, returns: 'Disposable' },
  { name: 'ide.createCompletionItemProvider', effect: 'DURABLE', description: 'Create a completion item provider', params: { provider: 'CompletionItemProvider' }, returns: 'Disposable' },
  { name: 'ide.createDefinitionProvider', effect: 'DURABLE', description: 'Create a definition provider', params: { provider: 'DefinitionProvider' }, returns: 'Disposable' },
  { name: 'ide.createHoverProvider', effect: 'DURABLE', description: 'Create a hover provider', params: { provider: 'HoverProvider' }, returns: 'Disposable' },
  { name: 'ide.createSignatureHelpProvider', effect: 'DURABLE', description: 'Create a signature help provider', params: { provider: 'SignatureHelpProvider' }, returns: 'Disposable' },
  { name: 'ide.createReferenceProvider', effect: 'DURABLE', description: 'Create a reference provider', params: { provider: 'ReferenceProvider' }, returns: 'Disposable' },
  { name: 'ide.createDocumentSymbolProvider', effect: 'DURABLE', description: 'Create a document symbol provider', params: { provider: 'DocumentSymbolProvider' }, returns: 'Disposable' },
  { name: 'ide.createWorkspaceSymbolProvider', effect: 'DURABLE', description: 'Create a workspace symbol provider', params: { provider: 'WorkspaceSymbolProvider' }, returns: 'Disposable' },
  { name: 'ide.createCodeLensProvider', effect: 'DURABLE', description: 'Create a code lens provider', params: { provider: 'CodeLensProvider' }, returns: 'Disposable' },
  { name: 'ide.createDocumentFormattingEditProvider', effect: 'DURABLE', description: 'Create a document formatting provider', params: { provider: 'DocumentFormattingEditProvider' }, returns: 'Disposable' },
  { name: 'ide.createDocumentRangeFormattingEditProvider', effect: 'DURABLE', description: 'Create a range formatting provider', params: { provider: 'DocumentRangeFormattingEditProvider' }, returns: 'Disposable' },
  { name: 'ide.createOnTypeFormattingEditProvider', effect: 'DURABLE', description: 'Create an on-type formatting provider', params: { provider: 'OnTypeFormattingEditProvider' }, returns: 'Disposable' },
  { name: 'ide.createRenameProvider', effect: 'DURABLE', description: 'Create a rename provider', params: { provider: 'RenameProvider' }, returns: 'Disposable' },
  { name: 'ide.createDocumentSemanticTokensProvider', effect: 'DURABLE', description: 'Create a semantic tokens provider', params: { provider: 'DocumentSemanticTokensProvider' }, returns: 'Disposable' },
  { name: 'ide.createDocumentRangeSemanticTokensProvider', effect: 'DURABLE', description: 'Create a range semantic tokens provider', params: { provider: 'DocumentRangeSemanticTokensProvider' }, returns: 'Disposable' },
  { name: 'ide.createFoldingRangeProvider', effect: 'DURABLE', description: 'Create a folding range provider', params: { provider: 'FoldingRangeProvider' }, returns: 'Disposable' },
  { name: 'ide.createSelectionRangeProvider', effect: 'DURABLE', description: 'Create a selection range provider', params: { provider: 'SelectionRangeProvider' }, returns: 'Disposable' },
  { name: 'ide.createCallHierarchyProvider', effect: 'DURABLE', description: 'Create a call hierarchy provider', params: { provider: 'CallHierarchyProvider' }, returns: 'Disposable' },
  { name: 'ide.createTypeHierarchyProvider', effect: 'DURABLE', description: 'Create a type hierarchy provider', params: { provider: 'TypeHierarchyProvider' }, returns: 'Disposable' },
  { name: 'ide.createLinkedEditingRangeProvider', effect: 'DURABLE', description: 'Create a linked editing range provider', params: { provider: 'LinkedEditingRangeProvider' }, returns: 'Disposable' },
  { name: 'ide.createColorProvider', effect: 'DURABLE', description: 'Create a color provider', params: { provider: 'DocumentColorProvider' }, returns: 'Disposable' },
  { name: 'ide.createInlayHintsProvider', effect: 'DURABLE', description: 'Create an inlay hints provider', params: { provider: 'InlayHintsProvider' }, returns: 'Disposable' },
  { name: 'ide.createInlineValuesProvider', effect: 'DURABLE', description: 'Create an inline values provider', params: { provider: 'InlineValuesProvider' }, returns: 'Disposable' },
  { name: 'ide.createEvaluatableExpressionProvider', effect: 'DURABLE', description: 'Create an evaluatable expression provider', params: { provider: 'EvaluatableExpressionProvider' }, returns: 'Disposable' },
  { name: 'ide.createPasteEditProvider', effect: 'DURABLE', description: 'Create a paste edit provider', params: { provider: 'PasteEditProvider' }, returns: 'Disposable' },
  { name: 'ide.createTerminalProfileProvider', effect: 'DURABLE', description: 'Create a terminal profile provider', params: { provider: 'TerminalProfileProvider' }, returns: 'Disposable' },
  { name: 'ide.createTerminalQuickFixProvider', effect: 'DURABLE', description: 'Create a terminal quick fix provider', params: { provider: 'TerminalQuickFixProvider' }, returns: 'Disposable' },
  { name: 'ide.createTerminalCompletionProvider', effect: 'DURABLE', description: 'Create a terminal completion provider', params: { provider: 'TerminalCompletionProvider' }, returns: 'Disposable' },
  { name: 'ide.createTerminalLinkProvider', effect: 'DURABLE', description: 'Create a terminal link provider', params: { provider: 'TerminalLinkProvider' }, returns: 'Disposable' },
  { name: 'ide.createTerminalLinkProvider2', effect: 'DURABLE', description: 'Create a terminal link provider (v2)', params: { provider: 'TerminalLinkProvider2' }, returns: 'Disposable' },
  { name: 'ide.createTaskProvider', effect: 'DURABLE', description: 'Create a task provider', params: { provider: 'TaskProvider' }, returns: 'Disposable' },
  { name: 'ide.createTestController', effect: 'DURABLE', description: 'Create a test controller', params: { controllerId: 'string', label: 'string' }, returns: 'TestController' },
  { name: 'ide.createTestRunProfile', effect: 'DURABLE', description: 'Create a test run profile', params: { controllerId: 'string', label: 'string', kind: 'TestRunProfileKind' }, returns: 'TestRunProfile' },
  { name: 'ide.createDebugAdapterDescriptor', effect: 'DURABLE', description: 'Create a debug adapter descriptor', params: { debugAdapter: 'DebugAdapter' }, returns: 'DebugAdapterDescriptor' },
  { name: 'ide.createDebugAdapterTracker', effect: 'DURABLE', description: 'Create a debug adapter tracker', params: { tracker: 'DebugAdapterTracker' }, returns: 'DebugAdapterTracker' },
  { name: 'ide.createDebugConfigurationProvider', effect: 'DURABLE', description: 'Create a debug configuration provider', params: { provider: 'DebugConfigurationProvider' }, returns: 'Disposable' },
  { name: 'ide.createDebugConsole', effect: 'DURABLE', description: 'Create a debug console', params: { console: 'DebugConsole' }, returns: 'DebugConsole' },
  { name: 'ide.createSCMProvider', effect: 'DURABLE', description: 'Create an SCM provider', params: { provider: 'SCMProvider' }, returns: 'Disposable' },
  { name: 'ide.createSCMGroup', effect: 'DURABLE', description: 'Create an SCM group', params: { group: 'SCMGroup' }, returns: 'Disposable' },
  { name: 'ide.createSCMResource', effect: 'DURABLE', description: 'Create an SCM resource', params: { resource: 'SCMResource' }, returns: 'Disposable' },
  { name: 'ide.createSCMResourceGroup', effect: 'DURABLE', description: 'Create an SCM resource group', params: { group: 'SCMResourceGroup' }, returns: 'Disposable' },
  { name: 'ide.createSCMHistoryItem', effect: 'DURABLE', description: 'Create an SCM history item', params: { item: 'SCMHistoryItem' }, returns: 'Disposable' },
  { name: 'ide.createSCMHistoryItemChange', effect: 'DURABLE', description: 'Create an SCM history item change', params: { change: 'SCMHistoryItemChange' }, returns: 'Disposable' },
  { name: 'ide.createSCMHistoryProvider', effect: 'DURABLE', description: 'Create an SCM history provider', params: { provider: 'SCMHistoryProvider' }, returns: 'Disposable' },
  { name: 'ide.createSCMQuickDiffProvider', effect: 'DURABLE', description: 'Create an SCM quick diff provider', params: { provider: 'SCMQuickDiffProvider' }, returns: 'Disposable' },
  { name: 'ide.createSCMInputBox', effect: 'DURABLE', description: 'Create an SCM input box', params: { inputBox: 'SCMInputBox' }, returns: 'Disposable' },
  { name: 'ide.createSCMProviderActionButton', effect: 'DURABLE', description: 'Create an SCM provider action button', params: { button: 'SCMProviderActionButton' }, returns: 'Disposable' },
  { name: 'ide.createSCMProviderActionButton2', effect: 'DURABLE', description: 'Create an SCM provider action button (v2)', params: { button: 'SCMProviderActionButton2' }, returns: 'Disposable' },
  { name: 'ide.createSCMProviderActionButton3', effect: 'DURABLE', description: 'Create an SCM provider action button (v3)', params: { button: 'SCMProviderActionButton3' }, returns: 'Disposable' },
  { name: 'ide.createSCMProviderActionButton4', effect: 'DURABLE', description: 'Create an SCM provider action button (v4)', params: { button: 'SCMProviderActionButton4' }, returns: 'Disposable' },
  { name: 'ide.createSCMProviderActionButton5', effect: 'DURABLE', description: 'Create an SCM provider action button (v5)', params: { button: 'SCMProviderActionButton5' }, returns: 'Disposable' },
];

// ---------------------------------------------------------------------------
// Result Types
// ---------------------------------------------------------------------------

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

/** Result of a refactor.list operation. */
export interface RefactorListResult {
  uri: string;
  range: { start: { line: number; character: number }; end: { line: number; character: number } };
  actions: RefactorActionSummary[];
}

/** Result of a refactor.apply operation. */
export interface RefactorApplyResult {
  applied: boolean;
  title: string;
  editCount: number;
}

// ---------------------------------------------------------------------------
// Capability Registry Instance
// ---------------------------------------------------------------------------

/**
 * Global capability registry with all IDE capabilities registered.
 * This is the single source of truth for capability discovery.
 */
export const capabilityRegistry = new CapabilityRegistry();

// Register all capability namespaces
capabilityRegistry.registerAll([
  ...workspaceCapabilities,
  ...editorCapabilities,
  ...symbolCapabilities,
  ...refactorCapabilities,
  ...diagnosticsCapabilities,
  ...taskCapabilities,
  ...testCapabilities,
  ...debugCapabilities,
  ...terminalCapabilities,
  ...scmCapabilities,
  ...ideCapabilities,
]);

// ---------------------------------------------------------------------------
// Command Resolver Instance
// ---------------------------------------------------------------------------

/**
 * Global command resolver for ide.executeCommand.
 * Resolves commands through VS Code's command system.
 */
export const commandResolver = new CommandResolver();

// ---------------------------------------------------------------------------
// Capability Namespace Exports
// ---------------------------------------------------------------------------

/** Workspace capabilities — file system and workspace operations. */
export const workspace = {
  readFile: workspaceCapabilities.find((c) => c.name === 'workspace.readFile')!,
  writeFile: workspaceCapabilities.find((c) => c.name === 'workspace.writeFile')!,
  listFiles: workspaceCapabilities.find((c) => c.name === 'workspace.listFiles')!,
  createDirectory: workspaceCapabilities.find((c) => c.name === 'workspace.createDirectory')!,
  deleteFile: workspaceCapabilities.find((c) => c.name === 'workspace.deleteFile')!,
  findFiles: workspaceCapabilities.find((c) => c.name === 'workspace.findFiles')!,
  getWorkspaceFolders: workspaceCapabilities.find((c) => c.name === 'workspace.getWorkspaceFolders')!,
  asRelativePath: workspaceCapabilities.find((c) => c.name === 'workspace.asRelativePath')!,
  openTextDocument: workspaceCapabilities.find((c) => c.name === 'workspace.openTextDocument')!,
  saveAll: workspaceCapabilities.find((c) => c.name === 'workspace.saveAll')!,
  applyEdit: workspaceCapabilities.find((c) => c.name === 'workspace.applyEdit')!,
  getConfiguration: workspaceCapabilities.find((c) => c.name === 'workspace.getConfiguration')!,
  updateConfiguration: workspaceCapabilities.find((c) => c.name === 'workspace.updateConfiguration')!,
  registerTextDocumentContentProvider: workspaceCapabilities.find((c) => c.name === 'workspace.registerTextDocumentContentProvider')!,
  onDidSaveTextDocument: workspaceCapabilities.find((c) => c.name === 'workspace.onDidSaveTextDocument')!,
  onDidOpenTextDocument: workspaceCapabilities.find((c) => c.name === 'workspace.onDidOpenTextDocument')!,
  onDidCloseTextDocument: workspaceCapabilities.find((c) => c.name === 'workspace.onDidCloseTextDocument')!,
  onDidChangeTextDocument: workspaceCapabilities.find((c) => c.name === 'workspace.onDidChangeTextDocument')!,
  onDidChangeConfiguration: workspaceCapabilities.find((c) => c.name === 'workspace.onDidChangeConfiguration')!,
};

/** Editor capabilities — text editor operations. */
export const editor = {
  openDocument: editorCapabilities.find((c) => c.name === 'editor.openDocument')!,
  closeDocument: editorCapabilities.find((c) => c.name === 'editor.closeDocument')!,
  saveDocument: editorCapabilities.find((c) => c.name === 'editor.saveDocument')!,
  getActiveEditor: editorCapabilities.find((c) => c.name === 'editor.getActiveEditor')!,
  getVisibleEditors: editorCapabilities.find((c) => c.name === 'editor.getVisibleEditors')!,
  showTextDocument: editorCapabilities.find((c) => c.name === 'editor.showTextDocument')!,
  editDocument: editorCapabilities.find((c) => c.name === 'editor.editDocument')!,
  insertSnippet: editorCapabilities.find((c) => c.name === 'editor.insertSnippet')!,
  setDecorations: editorCapabilities.find((c) => c.name === 'editor.setDecorations')!,
  revealRange: editorCapabilities.find((c) => c.name === 'editor.revealRange')!,
  getSelection: editorCapabilities.find((c) => c.name === 'editor.getSelection')!,
  setSelection: editorCapabilities.find((c) => c.name === 'editor.setSelection')!,
  getCursorPosition: editorCapabilities.find((c) => c.name === 'editor.getCursorPosition')!,
  setCursorPosition: editorCapabilities.find((c) => c.name === 'editor.setCursorPosition')!,
  getVisibleRanges: editorCapabilities.find((c) => c.name === 'editor.getVisibleRanges')!,
  getDocument: editorCapabilities.find((c) => c.name === 'editor.getDocument')!,
  getLanguageId: editorCapabilities.find((c) => c.name === 'editor.getLanguageId')!,
  executeFormatDocument: editorCapabilities.find((c) => c.name === 'editor.executeFormatDocument')!,
  executeFormatSelection: editorCapabilities.find((c) => c.name === 'editor.executeFormatSelection')!,
  executeRename: editorCapabilities.find((c) => c.name === 'editor.executeRename')!,
  executeDefinitionProvider: editorCapabilities.find((c) => c.name === 'editor.executeDefinitionProvider')!,
  executeTypeDefinitionProvider: editorCapabilities.find((c) => c.name === 'editor.executeTypeDefinitionProvider')!,
  executeImplementationProvider: editorCapabilities.find((c) => c.name === 'editor.executeImplementationProvider')!,
  executeHoverProvider: editorCapabilities.find((c) => c.name === 'editor.executeHoverProvider')!,
  executeDocumentSymbolProvider: editorCapabilities.find((c) => c.name === 'editor.executeDocumentSymbolProvider')!,
  executeCodeActionProvider: editorCapabilities.find((c) => c.name === 'editor.executeCodeActionProvider')!,
  executeCompletionItemProvider: editorCapabilities.find((c) => c.name === 'editor.executeCompletionItemProvider')!,
  executeSignatureHelpProvider: editorCapabilities.find((c) => c.name === 'editor.executeSignatureHelpProvider')!,
  executeLinkProvider: editorCapabilities.find((c) => c.name === 'editor.executeLinkProvider')!,
  executeColorProvider: editorCapabilities.find((c) => c.name === 'editor.executeColorProvider')!,
  executeFoldingRangeProvider: editorCapabilities.find((c) => c.name === 'editor.executeFoldingRangeProvider')!,
  executeSelectionRangeProvider: editorCapabilities.find((c) => c.name === 'editor.executeSelectionRangeProvider')!,
  executeCallHierarchyProvider: editorCapabilities.find((c) => c.name === 'editor.executeCallHierarchyProvider')!,
  executeDocumentHighlightProvider: editorCapabilities.find((c) => c.name === 'editor.executeDocumentHighlightProvider')!,
  executeReferenceProvider: editorCapabilities.find((c) => c.name === 'editor.executeReferenceProvider')!,
  executeCodeLensProvider: editorCapabilities.find((c) => c.name === 'editor.executeCodeLensProvider')!,
  executeInlineValueProvider: editorCapabilities.find((c) => c.name === 'editor.executeInlineValueProvider')!,
  executeInlayHintProvider: editorCapabilities.find((c) => c.name === 'editor.executeInlayHintProvider')!,
};

/** Symbol capabilities — symbol navigation and search. */
export const symbol = {
  find: symbolCapabilities.find((c) => c.name === 'symbol.find')!,
  references: symbolCapabilities.find((c) => c.name === 'symbol.references')!,
  rename: symbolCapabilities.find((c) => c.name === 'symbol.rename')!,
  workspaceSymbols: symbolCapabilities.find((c) => c.name === 'symbol.workspaceSymbols')!,
  definition: symbolCapabilities.find((c) => c.name === 'symbol.definition')!,
  typeDefinition: symbolCapabilities.find((c) => c.name === 'symbol.typeDefinition')!,
  implementation: symbolCapabilities.find((c) => c.name === 'symbol.implementation')!,
  hover: symbolCapabilities.find((c) => c.name === 'symbol.hover')!,
  documentSymbols: symbolCapabilities.find((c) => c.name === 'symbol.documentSymbols')!,
  documentHighlights: symbolCapabilities.find((c) => c.name === 'symbol.documentHighlights')!,
  callHierarchyIncoming: symbolCapabilities.find((c) => c.name === 'symbol.callHierarchyIncoming')!,
  callHierarchyOutgoing: symbolCapabilities.find((c) => c.name === 'symbol.callHierarchyOutgoing')!,
};

/** Refactor capabilities — code refactoring operations. */
export const refactor = {
  list: refactorCapabilities.find((c) => c.name === 'refactor.list')!,
  apply: refactorCapabilities.find((c) => c.name === 'refactor.apply')!,
  extractMethod: refactorCapabilities.find((c) => c.name === 'refactor.extractMethod')!,
  extractFunction: refactorCapabilities.find((c) => c.name === 'refactor.extractFunction')!,
  extractVariable: refactorCapabilities.find((c) => c.name === 'refactor.extractVariable')!,
  extractConstant: refactorCapabilities.find((c) => c.name === 'refactor.extractConstant')!,
  moveToNewFile: refactorCapabilities.find((c) => c.name === 'refactor.moveToNewFile')!,
  moveToClass: refactorCapabilities.find((c) => c.name === 'refactor.moveToClass')!,
  rewriteFunctionToClass: refactorCapabilities.find((c) => c.name === 'refactor.rewriteFunctionToClass')!,
  rewriteAddParameter: refactorCapabilities.find((c) => c.name === 'refactor.rewriteAddParameter')!,
  rewriteRemoveParameter: refactorCapabilities.find((c) => c.name === 'refactor.rewriteRemoveParameter')!,
  organizeImports: refactorCapabilities.find((c) => c.name === 'refactor.organizeImports')!,
  inlineVariable: refactorCapabilities.find((c) => c.name === 'refactor.inlineVariable')!,
  convertToAsync: refactorCapabilities.find((c) => c.name === 'refactor.convertToAsync')!,
  convertToArrow: refactorCapabilities.find((c) => c.name === 'refactor.convertToArrow')!,
  convertToTemplateLiteral: refactorCapabilities.find((c) => c.name === 'refactor.convertToTemplateLiteral')!,
  addJSDoc: refactorCapabilities.find((c) => c.name === 'refactor.addJSDoc')!,
  removeUnused: refactorCapabilities.find((c) => c.name === 'refactor.removeUnused')!,
  sortMembers: refactorCapabilities.find((c) => c.name === 'refactor.sortMembers')!,
};

/** Diagnostics capabilities — diagnostic reading and management. */
export const diagnostics = {
  read: diagnosticsCapabilities.find((c) => c.name === 'diagnostics.read')!,
  getForUri: diagnosticsCapabilities.find((c) => c.name === 'diagnostics.getForUri')!,
  getForEditor: diagnosticsCapabilities.find((c) => c.name === 'diagnostics.getForEditor')!,
  clear: diagnosticsCapabilities.find((c) => c.name === 'diagnostics.clear')!,
  getSeverityCount: diagnosticsCapabilities.find((c) => c.name === 'diagnostics.getSeverityCount')!,
  getErrors: diagnosticsCapabilities.find((c) => c.name === 'diagnostics.getErrors')!,
  getWarnings: diagnosticsCapabilities.find((c) => c.name === 'diagnostics.getWarnings')!,
  getHints: diagnosticsCapabilities.find((c) => c.name === 'diagnostics.getHints')!,
  getInformation: diagnosticsCapabilities.find((c) => c.name === 'diagnostics.getInformation')!,
  onDidChangeDiagnostics: diagnosticsCapabilities.find((c) => c.name === 'diagnostics.onDidChangeDiagnostics')!,
};

/** Task capabilities — task execution and management. */
export const task = {
  run: taskCapabilities.find((c) => c.name === 'task.run')!,
  fetch: taskCapabilities.find((c) => c.name === 'task.fetch')!,
  getDefaultBuildTask: taskCapabilities.find((c) => c.name === 'task.getDefaultBuildTask')!,
  getDefaultTestTask: taskCapabilities.find((c) => c.name === 'task.getDefaultTestTask')!,
  terminate: taskCapabilities.find((c) => c.name === 'task.terminate')!,
  restart: taskCapabilities.find((c) => c.name === 'task.restart')!,
  getActiveTasks: taskCapabilities.find((c) => c.name === 'task.getActiveTasks')!,
  registerTaskProvider: taskCapabilities.find((c) => c.name === 'task.registerTaskProvider')!,
  onDidStartTask: taskCapabilities.find((c) => c.name === 'task.onDidStartTask')!,
  onDidEndTask: taskCapabilities.find((c) => c.name === 'task.onDidEndTask')!,
  onDidStartTaskProcess: taskCapabilities.find((c) => c.name === 'task.onDidStartTaskProcess')!,
  onDidEndTaskProcess: taskCapabilities.find((c) => c.name === 'task.onDidEndTaskProcess')!,
};

/** Test capabilities — test execution and management. */
export const test = {
  run: testCapabilities.find((c) => c.name === 'test.run')!,
  target: testCapabilities.find((c) => c.name === 'test.target')!,
  coverage: testCapabilities.find((c) => c.name === 'test.coverage')!,
  createController: testCapabilities.find((c) => c.name === 'test.createController')!,
  getControllers: testCapabilities.find((c) => c.name === 'test.getControllers')!,
  getController: testCapabilities.find((c) => c.name === 'test.getController')!,
  getTestItem: testCapabilities.find((c) => c.name === 'test.getTestItem')!,
  getTestItems: testCapabilities.find((c) => c.name === 'test.getTestItems')!,
  createRunProfile: testCapabilities.find((c) => c.name === 'test.createRunProfile')!,
  refreshTests: testCapabilities.find((c) => c.name === 'test.refreshTests')!,
  runTestsFromProfile: testCapabilities.find((c) => c.name === 'test.runTestsFromProfile')!,
  onDidChangeTestResults: testCapabilities.find((c) => c.name === 'test.onDidChangeTestResults')!,
  onDidStartTestRun: testCapabilities.find((c) => c.name === 'test.onDidStartTestRun')!,
  onDidEndTestRun: testCapabilities.find((c) => c.name === 'test.onDidEndTestRun')!,
};

/** Debug capabilities — debugging operations. */
export const debug = {
  start: debugCapabilities.find((c) => c.name === 'debug.start')!,
  stop: debugCapabilities.find((c) => c.name === 'debug.stop')!,
  inspect: debugCapabilities.find((c) => c.name === 'debug.inspect')!,
  addBreakpoint: debugCapabilities.find((c) => c.name === 'debug.addBreakpoint')!,
  removeBreakpoint: debugCapabilities.find((c) => c.name === 'debug.removeBreakpoint')!,
  getBreakpoints: debugCapabilities.find((c) => c.name === 'debug.getBreakpoints')!,
  clearBreakpoints: debugCapabilities.find((c) => c.name === 'debug.clearBreakpoints')!,
  continue: debugCapabilities.find((c) => c.name === 'debug.continue')!,
  stepInto: debugCapabilities.find((c) => c.name === 'debug.stepInto')!,
  stepOver: debugCapabilities.find((c) => c.name === 'debug.stepOver')!,
  stepOut: debugCapabilities.find((c) => c.name === 'debug.stepOut')!,
  evaluate: debugCapabilities.find((c) => c.name === 'debug.evaluate')!,
  getStackFrames: debugCapabilities.find((c) => c.name === 'debug.getStackFrames')!,
  getScopes: debugCapabilities.find((c) => c.name === 'debug.getScopes')!,
  getVariables: debugCapabilities.find((c) => c.name === 'debug.getVariables')!,
  registerDebugConfigurationProvider: debugCapabilities.find((c) => c.name === 'debug.registerDebugConfigurationProvider')!,
  onDidStartDebugSession: debugCapabilities.find((c) => c.name === 'debug.onDidStartDebugSession')!,
  onDidEndDebugSession: debugCapabilities.find((c) => c.name === 'debug.onDidEndDebugSession')!,
  onDidChangeActiveDebugSession: debugCapabilities.find((c) => c.name === 'debug.onDidChangeActiveDebugSession')!,
  onDidReceiveDebugSessionCustomEvent: debugCapabilities.find((c) => c.name === 'debug.onDidReceiveDebugSessionCustomEvent')!,
  onDidChangeBreakpoints: debugCapabilities.find((c) => c.name === 'debug.onDidChangeBreakpoints')!,
};

/** Terminal capabilities — terminal operations. */
export const terminal = {
  run: terminalCapabilities.find((c) => c.name === 'terminal.run')!,
  create: terminalCapabilities.find((c) => c.name === 'terminal.create')!,
  sendText: terminalCapabilities.find((c) => c.name === 'terminal.sendText')!,
  show: terminalCapabilities.find((c) => c.name === 'terminal.show')!,
  hide: terminalCapabilities.find((c) => c.name === 'terminal.hide')!,
  dispose: terminalCapabilities.find((c) => c.name === 'terminal.dispose')!,
  getActive: terminalCapabilities.find((c) => c.name === 'terminal.getActive')!,
  getAll: terminalCapabilities.find((c) => c.name === 'terminal.getAll')!,
  getByName: terminalCapabilities.find((c) => c.name === 'terminal.getByName')!,
  registerTerminalProfileProvider: terminalCapabilities.find((c) => c.name === 'terminal.registerTerminalProfileProvider')!,
  registerTerminalLinkProvider: terminalCapabilities.find((c) => c.name === 'terminal.registerTerminalLinkProvider')!,
  onDidOpenTerminal: terminalCapabilities.find((c) => c.name === 'terminal.onDidOpenTerminal')!,
  onDidCloseTerminal: terminalCapabilities.find((c) => c.name === 'terminal.onDidCloseTerminal')!,
  onDidChangeTerminalState: terminalCapabilities.find((c) => c.name === 'terminal.onDidChangeTerminalState')!,
};

/** SCM capabilities — source control management. */
export const scm = {
  status: scmCapabilities.find((c) => c.name === 'scm.status')!,
  diff: scmCapabilities.find((c) => c.name === 'scm.diff')!,
  branch: scmCapabilities.find((c) => c.name === 'scm.branch')!,
  commit: scmCapabilities.find((c) => c.name === 'scm.commit')!,
  push: scmCapabilities.find((c) => c.name === 'scm.push')!,
  pull: scmCapabilities.find((c) => c.name === 'scm.pull')!,
  fetch: scmCapabilities.find((c) => c.name === 'scm.fetch')!,
  stage: scmCapabilities.find((c) => c.name === 'scm.stage')!,
  unstage: scmCapabilities.find((c) => c.name === 'scm.unstage')!,
  discard: scmCapabilities.find((c) => c.name === 'scm.discard')!,
  createBranch: scmCapabilities.find((c) => c.name === 'scm.createBranch')!,
  checkout: scmCapabilities.find((c) => c.name === 'scm.checkout')!,
  merge: scmCapabilities.find((c) => c.name === 'scm.merge')!,
  rebase: scmCapabilities.find((c) => c.name === 'scm.rebase')!,
  reset: scmCapabilities.find((c) => c.name === 'scm.reset')!,
  createPatch: scmCapabilities.find((c) => c.name === 'scm.createPatch')!,
  applyPatch: scmCapabilities.find((c) => c.name === 'scm.applyPatch')!,
  getInputBoxValue: scmCapabilities.find((c) => c.name === 'scm.getInputBoxValue')!,
  setInputBoxValue: scmCapabilities.find((c) => c.name === 'scm.setInputBoxValue')!,
  getSourceControl: scmCapabilities.find((c) => c.name === 'scm.getSourceControl')!,
  getSourceControls: scmCapabilities.find((c) => c.name === 'scm.getSourceControls')!,
  createSourceControl: scmCapabilities.find((c) => c.name === 'scm.createSourceControl')!,
  onDidChangeSourceControl: scmCapabilities.find((c) => c.name === 'scm.onDidChangeSourceControl')!,
};

/** IDE capabilities — VS Code IDE operations. */
export const ide = {
  executeCommand: ideCapabilities.find((c) => c.name === 'ide.executeCommand')!,
  getConfiguration: ideCapabilities.find((c) => c.name === 'ide.getConfiguration')!,
  setConfiguration: ideCapabilities.find((c) => c.name === 'ide.setConfiguration')!,
  showInformationMessage: ideCapabilities.find((c) => c.name === 'ide.showInformationMessage')!,
  showWarningMessage: ideCapabilities.find((c) => c.name === 'ide.showWarningMessage')!,
  showErrorMessage: ideCapabilities.find((c) => c.name === 'ide.showErrorMessage')!,
  showQuickPick: ideCapabilities.find((c) => c.name === 'ide.showQuickPick')!,
  showInputBox: ideCapabilities.find((c) => c.name === 'ide.showInputBox')!,
  createOutputChannel: ideCapabilities.find((c) => c.name === 'ide.createOutputChannel')!,
  registerCommand: ideCapabilities.find((c) => c.name === 'ide.registerCommand')!,
  registerTextEditorCommand: ideCapabilities.find((c) => c.name === 'ide.registerTextEditorCommand')!,
  getCommands: ideCapabilities.find((c) => c.name === 'ide.getCommands')!,
  hasCommand: ideCapabilities.find((c) => c.name === 'ide.hasCommand')!,
  createStatusBarItem: ideCapabilities.find((c) => c.name === 'ide.createStatusBarItem')!,
  createTreeView: ideCapabilities.find((c) => c.name === 'ide.createTreeView')!,
  createWebviewPanel: ideCapabilities.find((c) => c.name === 'ide.createWebviewPanel')!,
  createTerminal: ideCapabilities.find((c) => c.name === 'ide.createTerminal')!,
  createQuickPick: ideCapabilities.find((c) => c.name === 'ide.createQuickPick')!,
  createInputBox: ideCapabilities.find((c) => c.name === 'ide.createInputBox')!,
  createLanguageStatusItem: ideCapabilities.find((c) => c.name === 'ide.createLanguageStatusItem')!,
  createDiagnosticCollection: ideCapabilities.find((c) => c.name === 'ide.createDiagnosticCollection')!,
  createDecorationType: ideCapabilities.find((c) => c.name === 'ide.createDecorationType')!,
  createFileDecorationProvider: ideCapabilities.find((c) => c.name === 'ide.createFileDecorationProvider')!,
  createDocumentLinkProvider: ideCapabilities.find((c) => c.name === 'ide.createDocumentLinkProvider')!,
  createCodeActionProvider: ideCapabilities.find((c) => c.name === 'ide.createCodeActionProvider')!,
  createCompletionItemProvider: ideCapabilities.find((c) => c.name === 'ide.createCompletionItemProvider')!,
  createDefinitionProvider: ideCapabilities.find((c) => c.name === 'ide.createDefinitionProvider')!,
  createHoverProvider: ideCapabilities.find((c) => c.name === 'ide.createHoverProvider')!,
  createSignatureHelpProvider: ideCapabilities.find((c) => c.name === 'ide.createSignatureHelpProvider')!,
  createReferenceProvider: ideCapabilities.find((c) => c.name === 'ide.createReferenceProvider')!,
  createDocumentSymbolProvider: ideCapabilities.find((c) => c.name === 'ide.createDocumentSymbolProvider')!,
  createWorkspaceSymbolProvider: ideCapabilities.find((c) => c.name === 'ide.createWorkspaceSymbolProvider')!,
  createCodeLensProvider: ideCapabilities.find((c) => c.name === 'ide.createCodeLensProvider')!,
  createDocumentFormattingEditProvider: ideCapabilities.find((c) => c.name === 'ide.createDocumentFormattingEditProvider')!,
  createDocumentRangeFormattingEditProvider: ideCapabilities.find((c) => c.name === 'ide.createDocumentRangeFormattingEditProvider')!,
  createOnTypeFormattingEditProvider: ideCapabilities.find((c) => c.name === 'ide.createOnTypeFormattingEditProvider')!,
  createRenameProvider: ideCapabilities.find((c) => c.name === 'ide.createRenameProvider')!,
  createDocumentSemanticTokensProvider: ideCapabilities.find((c) => c.name === 'ide.createDocumentSemanticTokensProvider')!,
  createDocumentRangeSemanticTokensProvider: ideCapabilities.find((c) => c.name === 'ide.createDocumentRangeSemanticTokensProvider')!,
  createFoldingRangeProvider: ideCapabilities.find((c) => c.name === 'ide.createFoldingRangeProvider')!,
  createSelectionRangeProvider: ideCapabilities.find((c) => c.name === 'ide.createSelectionRangeProvider')!,
  createCallHierarchyProvider: ideCapabilities.find((c) => c.name === 'ide.createCallHierarchyProvider')!,
  createTypeHierarchyProvider: ideCapabilities.find((c) => c.name === 'ide.createTypeHierarchyProvider')!,
  createLinkedEditingRangeProvider: ideCapabilities.find((c) => c.name === 'ide.createLinkedEditingRangeProvider')!,
  createColorProvider: ideCapabilities.find((c) => c.name === 'ide.createColorProvider')!,
  createInlayHintsProvider: ideCapabilities.find((c) => c.name === 'ide.createInlayHintsProvider')!,
  createInlineValuesProvider: ideCapabilities.find((c) => c.name === 'ide.createInlineValuesProvider')!,
  createEvaluatableExpressionProvider: ideCapabilities.find((c) => c.name === 'ide.createEvaluatableExpressionProvider')!,
  createPasteEditProvider: ideCapabilities.find((c) => c.name === 'ide.createPasteEditProvider')!,
  createTerminalProfileProvider: ideCapabilities.find((c) => c.name === 'ide.createTerminalProfileProvider')!,
  createTerminalQuickFixProvider: ideCapabilities.find((c) => c.name === 'ide.createTerminalQuickFixProvider')!,
  createTerminalCompletionProvider: ideCapabilities.find((c) => c.name === 'ide.createTerminalCompletionProvider')!,
  createTerminalLinkProvider: ideCapabilities.find((c) => c.name === 'ide.createTerminalLinkProvider')!,
  createTerminalLinkProvider2: ideCapabilities.find((c) => c.name === 'ide.createTerminalLinkProvider2')!,
  createTaskProvider: ideCapabilities.find((c) => c.name === 'ide.createTaskProvider')!,
  createTestController: ideCapabilities.find((c) => c.name === 'ide.createTestController')!,
  createTestRunProfile: ideCapabilities.find((c) => c.name === 'ide.createTestRunProfile')!,
  createDebugAdapterDescriptor: ideCapabilities.find((c) => c.name === 'ide.createDebugAdapterDescriptor')!,
  createDebugAdapterTracker: ideCapabilities.find((c) => c.name === 'ide.createDebugAdapterTracker')!,
  createDebugConfigurationProvider: ideCapabilities.find((c) => c.name === 'ide.createDebugConfigurationProvider')!,
  createDebugConsole: ideCapabilities.find((c) => c.name === 'ide.createDebugConsole')!,
  createSCMProvider: ideCapabilities.find((c) => c.name === 'ide.createSCMProvider')!,
  createSCMGroup: ideCapabilities.find((c) => c.name === 'ide.createSCMGroup')!,
  createSCMResource: ideCapabilities.find((c) => c.name === 'ide.createSCMResource')!,
  createSCMResourceGroup: ideCapabilities.find((c) => c.name === 'ide.createSCMResourceGroup')!,
  createSCMHistoryItem: ideCapabilities.find((c) => c.name === 'ide.createSCMHistoryItem')!,
  createSCMHistoryItemChange: ideCapabilities.find((c) => c.name === 'ide.createSCMHistoryItemChange')!,
  createSCMHistoryProvider: ideCapabilities.find((c) => c.name === 'ide.createSCMHistoryProvider')!,
  createSCMQuickDiffProvider: ideCapabilities.find((c) => c.name === 'ide.createSCMQuickDiffProvider')!,
  createSCMInputBox: ideCapabilities.find((c) => c.name === 'ide.createSCMInputBox')!,
  createSCMProviderActionButton: ideCapabilities.find((c) => c.name === 'ide.createSCMProviderActionButton')!,
  createSCMProviderActionButton2: ideCapabilities.find((c) => c.name === 'ide.createSCMProviderActionButton2')!,
  createSCMProviderActionButton3: ideCapabilities.find((c) => c.name === 'ide.createSCMProviderActionButton3')!,
  createSCMProviderActionButton4: ideCapabilities.find((c) => c.name === 'ide.createSCMProviderActionButton4')!,
  createSCMProviderActionButton5: ideCapabilities.find((c) => c.name === 'ide.createSCMProviderActionButton5')!,
};

// ---------------------------------------------------------------------------
// Re-exports
// ---------------------------------------------------------------------------

export { RiskLevel } from '../authority/policy';
