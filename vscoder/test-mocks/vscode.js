// Mock vscode module for code-mode testing outside extension host
const listeners = [];
module.exports = {
  Uri: { file: (p) => ({ fsPath: p, toString: () => 'file:///' + p }) },
  window: {
    activeTextEditor: undefined,
    showTextDocument: async (uri) => ({ uri }),
    showWarningMessage: async (msg, ...opts) => opts[0], // auto-allow
  },
  workspace: {
    workspaceFolders: [{ uri: { fsPath: 'C:/æ/vscoder' } }],
  },
  languages: {
    getDiagnostics: () => [],
  },
  commands: {
    executeCommand: async (cmd, ...args) => ({ cmd, args }),
  },
  tasks: {
    executeTask: async (task) => true,
  },
  Task: class Task { constructor(...args) { this.args = args; } },
  TaskScope: { Workspace: 2 },
  DiagnosticSeverity: { Error: 0, Warning: 1, Information: 2, Hint: 3 },
};
