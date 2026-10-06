// VSCODER:// vendor shims for browser-based WebMCP tools
// These provide browser-compatible interfaces for Node.js built-ins
// so the same tool code can run in both VS Code extension host and browser.

// ── vscode shim ──
export const workspace = {
  workspaceFolders: [],
  getConfiguration: () => ({ get: () => undefined }),
  applyEdit: async () => true,
  openTextDocument: async () => ({}),
};

export const window = {
  activeTextEditor: undefined,
  visibleTextEditors: [],
  createWebviewPanel: () => ({ webview: { html: '', postMessage: () => {}, onDidReceiveMessage: () => {} }, dispose: () => {} }),
  showInformationMessage: () => {},
  showWarningMessage: () => {},
  showErrorMessage: () => {},
  createTerminal: () => ({ sendText: () => {}, show: () => {}, dispose: () => {} }),
};

export const commands = {
  executeCommand: async () => undefined,
};

export const languages = {
  getDiagnostics: () => [],
};

export const debug = {
  startDebugging: async () => true,
  breakpoints: [],
};

export const SymbolKind = {};
export const CodeActionKind = { RefactorExtract: 'refactor.extract', RefactorMove: 'refactor.move', RefactorRewrite: 'refactor.rewrite', SourceOrganizeImports: 'source.organizeImports' };
export const TestRunProfileKind = { Run: 1, Debug: 2, Coverage: 3 };
export const ViewColumn = { One: 1, Beside: -2 };
export const TaskScope = { Workspace: 1 };
export const DiagnosticSeverity = { Error: 0, Warning: 1, Information: 2, Hint: 3 };

export class Position {
  constructor(public line: number, public character: number) {}
}

export class Range {
  constructor(public start: Position, public end: Position) {}
}

export class Location {
  constructor(public uri: any, public range: Range) {}
}

export class WorkspaceEdit {
  size = 0;
  replace() {}
  insert() {}
  delete() {}
}

export class CodeAction {
  title = '';
  kind: any;
  edit: any;
  command: any;
  isPreferred = false;
}

export class Task {
  constructor(public definition: any, public scope: any, public name: string, public source: string, public execution: any) {}
}

export class ShellExecution {
  constructor(public args: any[]) {}
}

export class Uri {
  static file(path: string) { return { fsPath: path, toString: () => `file://${path}` }; }
  static parse(value: string) { return { fsPath: value, toString: () => value }; }
}

export const extensions = {
  getExtension: () => undefined,
};

export const scm = {
  sourceControls: [],
};

export default {
  workspace, window, commands, languages, debug,
  SymbolKind, CodeActionKind, TestRunProfileKind, ViewColumn,
  TaskScope, DiagnosticSeverity, Position, Range, Location,
  WorkspaceEdit, CodeAction, Task, ShellExecution, Uri, extensions, scm,
};