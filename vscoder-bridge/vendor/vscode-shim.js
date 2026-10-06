// VSCODER://BRIDGE — VS Code API shim for browser/webview context
(function() {
  const _commands = new Map();
  const _workspaceFolders = [];
  const _visibleTextEditors = [];
  const _diagnostics = [];
  const _terminals = [];
  const _breakpoints = [];

  class Position {
    constructor(line, character) { this.line = line; this.character = character; }
    with(change) { return new Position(change.line ?? this.line, change.character ?? this.character); }
    translate(change) { return new Position(this.line + (change.lineDelta ?? 0), this.character + (change.characterDelta ?? 0)); }
    isEqual(other) { return this.line === other.line && this.character === other.character; }
    isBefore(other) { return this.line < other.line || (this.line === other.line && this.character < other.character); }
    isBeforeOrEqual(other) { return this.isBefore(other) || this.isEqual(other); }
    isAfter(other) { return !this.isBeforeOrEqual(other); }
    isAfterOrEqual(other) { return !this.isBefore(other); }
    compareTo(other) { return this.line - other.line || this.character - other.character; }
  }

  class Range {
    constructor(start, end) { this.start = start; this.end = end; }
    with(change) { return new Range(change.start ?? this.start, change.end ?? this.end); }
    translate(change) { return new Range(this.start.translate(change), this.end.translate(change)); }
    isEqual(other) { return this.start.isEqual(other.start) && this.end.isEqual(other.end); }
    contains() { return false; }
    isEmpty() { return this.start.isEqual(this.end); }
    isSingleLine() { return this.start.line === this.end.line; }
    union() { return this; }
    intersection() { return this; }
  }

  class Location {
    constructor(uri, rangeOrPosition) { this.uri = uri; this.range = rangeOrPosition; }
  }

  class Breakpoint {
    constructor(enabled, condition, hitCondition, logMessage) {
      this.enabled = enabled; this.condition = condition;
      this.hitCondition = hitCondition; this.logMessage = logMessage;
    }
  }

  class SourceBreakpoint extends Breakpoint {
    constructor(location, enabled, condition, hitCondition, logMessage) {
      super(enabled, condition, hitCondition, logMessage);
      this.location = location;
    }
  }

  class FunctionBreakpoint extends Breakpoint {
    constructor(functionName, enabled, condition, hitCondition, logMessage) {
      super(enabled, condition, hitCondition, logMessage);
      this.functionName = functionName;
    }
  }

  class DataBreakpoint extends Breakpoint {
    constructor(label, dataId, canPersist, enabled, condition, hitCondition, logMessage) {
      super(enabled, condition, hitCondition, logMessage);
      this.label = label; this.dataId = dataId; this.canPersist = canPersist;
    }
  }

  class ExceptionBreakpoint extends Breakpoint {
    constructor(filter, label, enabled, condition, hitCondition, logMessage) {
      super(enabled, condition, hitCondition, logMessage);
      this.filter = filter; this.label = label;
    }
  }

  class InstructionBreakpoint extends Breakpoint {
    constructor(instructionReference, offset, enabled, condition, hitCondition, logMessage) {
      super(enabled, condition, hitCondition, logMessage);
      this.instructionReference = instructionReference; this.offset = offset;
    }
  }

  class WorkspaceEdit {
    constructor() { this._edits = []; }
    size() { return this._edits.length; }
    set(uri, edits) { this._edits.push({ uri, edits }); }
    get(uri) { return this._edits.find(e => e.uri === uri)?.edits || []; }
    has(uri) { return this._edits.some(e => e.uri === uri); }
    delete(uri) { this._edits = this._edits.filter(e => e.uri !== uri); }
    replace(uri, range, newText) { this._edits.push({ uri, range, newText }); }
    insert(uri, position, newText) { this._edits.push({ uri, position, newText }); }
    createFile(uri, options) { this._edits.push({ uri, options, isCreate: true }); }
    deleteFile(uri, options) { this._edits.push({ uri, options, isDelete: true }); }
    renameFile(oldUri, newUri, options) { this._edits.push({ oldUri, newUri, options, isRename: true }); }
    forEach(cb) { this._edits.forEach(e => cb(e.uri, e.edits)); }
    [Symbol.iterator]() { return this._edits[Symbol.iterator](); }
  }

  class Task {
    constructor(definition, scope, name, source, execution, problemMatchers) {
      this.definition = definition; this.scope = scope; this.name = name;
      this.source = source; this.execution = execution; this.problemMatchers = problemMatchers || [];
      this.runOptions = { reevaluateOnRerun: false };
      this.group = undefined; this.detail = undefined; this.isBackground = false;
      this.presentationOptions = {};
    }
  }

  class ShellExecution {
    constructor(commandLine, options) { this.commandLine = commandLine; this.options = options; }
  }

  class ProcessExecution {
    constructor(process, args, options) { this.process = process; this.args = args; this.options = options; }
  }

  class CancellationTokenSource {
    constructor() { this.token = { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) }; }
    cancel() {} dispose() {}
  }

  class EventEmitter {
    constructor() { this._listeners = []; }
    get event() { return (listener) => { this._listeners.push(listener); return { dispose: () => {} }; }; }
    fire(data) { this._listeners.forEach(l => l(data)); }
    dispose() { this._listeners = []; }
  }

  class Disposable {
    constructor(callOnDispose) { this._callOnDispose = callOnDispose; }
    dispose() { if (this._callOnDispose) this._callOnDispose(); }
    static from(...disposables) { return new Disposable(() => disposables.forEach(d => d.dispose())); }
  }

  class MarkdownString {
    constructor(value) { this.value = value || ''; }
    appendText(value) { this.value += value; return this; }
    appendMarkdown(value) { this.value += value; return this; }
    appendCodeblock(value, language) { this.value += '```' + (language || '') + '\n' + value + '\n```'; return this; }
  }

  class ThemeIcon {
    constructor(id) { this.id = id; }
    static File = new ThemeIcon('file');
    static Folder = new ThemeIcon('folder');
  }

  class ThemeColor {
    constructor(id) { this.id = id; }
  }

  class TreeItem {
    constructor(label, collapsibleState) { this.label = label; this.collapsibleState = collapsibleState; }
  }

  class RelativePattern {
    constructor(base, pattern) { this.base = base; this.pattern = pattern; }
  }

  class CancellationToken {
    constructor() { this.isCancellationRequested = false; this.onCancellationRequested = () => ({ dispose: () => {} }); }
  }

  class ProgressOptions {
    constructor(location, title, cancellable) { this.location = location; this.title = title; this.cancellable = cancellable; }
  }

  class QuickPickItem {
    constructor(label, description, detail) { this.label = label; this.description = description; this.detail = detail; }
  }

  class QuickPick {
    constructor() { this.items = []; this.value = ''; this.placeholder = ''; this.canSelectMany = false; this.matchOnDescription = false; this.matchOnDetail = false; this.ignoreFocusOut = false; this.step = 0; this.totalSteps = 0; this.enabled = true; this.busy = false; this.title = ''; this.buttons = []; this.activeItems = []; this.selectedItems = []; }
    show() { return Promise.resolve(undefined); } hide() {}
    onDidAccept() { return { dispose: () => {} }; }
    onDidTriggerButton() { return { dispose: () => {} }; }
    onDidTriggerItemButton() { return { dispose: () => {} }; }
    onDidChangeValue() { return { dispose: () => {} }; }
    onDidChangeActive() { return { dispose: () => {} }; }
    onDidChangeSelection() { return { dispose: () => {} }; }
    onDidHide() { return { dispose: () => {} }; }
    dispose() {}
  }

  class InputBox {
    constructor() { this.value = ''; this.placeholder = ''; this.password = false; this.prompt = ''; this.title = ''; this.step = 0; this.totalSteps = 0; this.enabled = true; this.busy = false; this.validationMessage = ''; this.buttons = []; }
    show() { return Promise.resolve(undefined); } hide() {}
    onDidAccept() { return { dispose: () => {} }; }
    onDidChangeValue() { return { dispose: () => {} }; }
    onDidTriggerButton() { return { dispose: () => {} }; }
    onDidHide() { return { dispose: () => {} }; }
    dispose() {}
  }

  class OpenDialogOptions {
    constructor() { this.canSelectFiles = true; this.canSelectFolders = false; this.canSelectMany = false; this.filters = {}; this.openLabel = ''; this.title = ''; this.defaultUri = undefined; }
  }

  class SaveDialogOptions {
    constructor() { this.filters = {}; this.saveLabel = ''; this.title = ''; this.defaultUri = undefined; }
  }

  class MessageOptions {
    constructor() { this.modal = false; this.detail = ''; }
  }

  class MessageItem {
    constructor(title, isCloseAffordance) { this.title = title; this.isCloseAffordance = isCloseAffordance; }
  }

  class TerminalLinkContext {
    constructor() { this.line = ''; this.terminal = undefined; }
  }

  class TerminalLink {
    constructor(startIndex, length, tooltip) { this.startIndex = startIndex; this.length = length; this.tooltip = tooltip; }
  }

  class TerminalProfile {
    constructor(options) { this.options = options; }
  }

  class TerminalQuickFix {
    constructor(terminalCommand) { this.terminalCommand = terminalCommand; }
  }

  class TerminalCompletionItem {
    constructor(label, documentation, iconPath) { this.label = label; this.documentation = documentation; this.iconPath = iconPath; }
  }

  class TerminalAction {
    constructor(title, icon, command) { this.title = title; this.icon = icon; this.command = command; }
  }

  class TerminalIcon {
    constructor(id) { this.id = id; }
  }

  class TerminalDecoration {
    constructor() { this.iconPath = undefined; this.color = undefined; this.overviewRulerColor = undefined; }
  }

  class TerminalShellIntegration {
    constructor() { this.executeCommand = () => Promise.resolve({ exitCode: 0, output: '' }); }
  }

  class TerminalShellExecution {
    constructor(commandLine, cwd) { this.commandLine = commandLine; this.cwd = cwd; }
  }

  class TerminalShellExecutionStartEvent {
    constructor() { this.terminal = undefined; this.execution = undefined; }
  }

  class TerminalShellExecutionEndEvent {
    constructor() { this.terminal = undefined; this.execution = undefined; this.exitCode = 0; }
  }

  class TerminalShellIntegrationChangeEvent {
    constructor() { this.terminal = undefined; }
  }

  class TerminalEnvironment {
    constructor() { this.value = ''; }
  }

  class TerminalEnvironmentVariableCollection {
    constructor() { this._vars = new Map(); }
    get(key) { return this._vars.get(key); }
    set(key, value) { this._vars.set(key, value); }
    delete(key) { this._vars.delete(key); }
    clear() { this._vars.clear(); }
    forEach(cb) { this._vars.forEach(cb); }
    [Symbol.iterator]() { return this._vars[Symbol.iterator](); }
    get size() { return this._vars.size; }
  }

  class TerminalOptions {
    constructor() { this.name = ''; this.shellPath = ''; this.shellArgs = []; this.cwd = ''; this.env = {}; this.strictEnv = false; this.hideFromUser = false; this.message = ''; this.isTransient = false; this.iconPath = undefined; this.color = undefined; this.overviewRulerColor = undefined; this.shellIntegration = undefined; }
  }

  class ExtensionTerminalOptions {
    constructor() { this.name = ''; this.iconPath = undefined; this.color = undefined; this.overviewRulerColor = undefined; this.shellIntegration = undefined; }
  }

  class Pseudoterminal {
    constructor() { this.onDidWrite = undefined; this.onDidClose = undefined; this.onDidChangeName = undefined; }
    open() {} close() {} handleInput() {}
  }

  class TerminalEditorLocationOptions {
    constructor() { this.viewColumn = 1; this.preserveFocus = false; }
  }

  class TerminalSplitLocationOptions {
    constructor() { this.parentTerminal = undefined; }
  }

  class TerminalLinkProvider {
    constructor() { this.provideTerminalLinks = undefined; this.handleTerminalLink = undefined; }
  }

  class TerminalProfileProvider {
    constructor() { this.provideTerminalProfile = undefined; }
  }

  class TerminalQuickFixProvider {
    constructor() { this.provideTerminalQuickFixes = undefined; }
  }

  class TerminalCompletionProvider {
    constructor() { this.provideTerminalCompletions = undefined; }
  }

  class TerminalActionProvider {
    constructor() { this.provideTerminalActions = undefined; }
  }

  class TerminalIconProvider {
    constructor() { this.provideTerminalIcon = undefined; }
  }

  class TerminalDecorationProvider {
    constructor() { this.provideTerminalDecoration = undefined; }
  }

  class TerminalShellIntegrationProvider {
    constructor() { this.provideTerminalShellIntegration = undefined; }
  }

  class TestRunRequest {
    constructor(include, exclude, profile) { this.include = include; this.exclude = exclude; this.profile = profile; }
  }

  class TestItem {
    constructor(id, label, uri) { this.id = id; this.label = label; this.uri = uri; this.children = []; }
  }

  class TestRun {
    constructor(name, persist) { this.name = name; this.persist = persist; }
  }

  class TestController {
    constructor(id, label) {
      this.id = id; this.label = label;
      this.items = { forEach: () => {}, get: () => undefined, size: 0, replace: () => {}, add: () => {}, delete: () => {} };
    }
    createTestRun() { return new TestRun('', true); }
    createRunProfile(label, kind, runHandler, isDefault) { return { label, kind, runHandler, isDefault, dispose: () => {} }; }
    refreshTests() { return Promise.resolve(); }
    dispose() {}
    invalidateTestResults() {}
  }

  class DebugConfiguration {
    constructor(type, name, request) { this.type = type; this.name = name; this.request = request; }
  }

  class DebugSession {
    constructor(id, type, name, workspaceFolder, configuration) {
      this.id = id; this.type = type; this.name = name;
      this.workspaceFolder = workspaceFolder; this.configuration = configuration;
    }
  }

  class SymbolInformation {
    constructor(name, kind, containerName, location) {
      this.name = name; this.kind = kind; this.containerName = containerName; this.location = location;
    }
  }

  class DocumentSymbol {
    constructor(name, detail, kind, range, selectionRange) {
      this.name = name; this.detail = detail; this.kind = kind; this.range = range; this.selectionRange = selectionRange;
      this.children = [];
    }
  }

  class Diagnostic {
    constructor(range, message, severity) { this.range = range; this.message = message; this.severity = severity; }
  }

  class CodeAction {
    constructor(title, kind) { this.title = title; this.kind = kind; }
  }

  class CodeActionKind {
    constructor(value) { this.value = value; }
    static QuickFix = new CodeActionKind('quickfix');
    static Refactor = new CodeActionKind('refactor');
    static RefactorExtract = new CodeActionKind('refactor.extract');
    static RefactorInline = new CodeActionKind('refactor.inline');
    static RefactorMove = new CodeActionKind('refactor.move');
    static RefactorRewrite = new CodeActionKind('refactor.rewrite');
    static Source = new CodeActionKind('source');
    static SourceOrganizeImports = new CodeActionKind('source.organizeImports');
    static SourceFixAll = new CodeActionKind('source.fixAll');
  }

  const vscode = {
    Position, Range, Location, Breakpoint, SourceBreakpoint, FunctionBreakpoint,
    DataBreakpoint, ExceptionBreakpoint, InstructionBreakpoint,
    WorkspaceEdit, Task, ShellExecution, ProcessExecution,
    CancellationTokenSource, EventEmitter, Disposable, MarkdownString,
    ThemeIcon, ThemeColor, TreeItem, RelativePattern, CancellationToken,
    ProgressOptions, QuickPickItem, QuickPick, InputBox,
    OpenDialogOptions, SaveDialogOptions, MessageOptions, MessageItem,
    TerminalLinkContext, TerminalLink, TerminalProfile, TerminalQuickFix,
    TerminalCompletionItem, TerminalAction, TerminalIcon, TerminalDecoration,
    TerminalShellIntegration, TerminalShellExecution, TerminalShellExecutionStartEvent,
    TerminalShellExecutionEndEvent, TerminalShellIntegrationChangeEvent,
    TerminalEnvironment, TerminalEnvironmentVariableCollection,
    TerminalOptions, ExtensionTerminalOptions, Pseudoterminal,
    TerminalEditorLocationOptions, TerminalSplitLocationOptions,
    TerminalLinkProvider, TerminalProfileProvider, TerminalQuickFixProvider,
    TerminalCompletionProvider, TerminalActionProvider, TerminalIconProvider,
    TerminalDecorationProvider, TerminalShellIntegrationProvider,
    TestRunRequest, TestItem, TestRun, TestController,
    DebugConfiguration, DebugSession, SymbolInformation, DocumentSymbol,
    Diagnostic, CodeAction, CodeActionKind,
    SymbolKind: {
      File: 0, Module: 1, Namespace: 2, Package: 3, Class: 4, Method: 5, Property: 6, Field: 7,
      Constructor: 8, Enum: 9, Interface: 10, Function: 11, Variable: 12, Constant: 13,
      String: 14, Number: 15, Boolean: 16, Array: 17, Object: 18, Key: 19, Null: 20,
      EnumMember: 21, Struct: 22, Event: 23, Operator: 24, TypeParameter: 25,
    },
    DiagnosticSeverity: { Error: 0, Warning: 1, Information: 2, Hint: 3 },
    TaskScope: { Global: 1, Workspace: 2 },
    TaskGroup: { Build: 'build', Test: 'test', Clean: 'clean', Rebuild: 'rebuild', Default: 'default' },
    TestRunProfileKind: { Run: 1, Debug: 2, Coverage: 3 },
    TreeItemCollapsibleState: { None: 0, Collapsed: 1, Expanded: 2 },
    ViewColumn: { Active: -1, Beside: -2, One: 1, Two: 2, Three: 3, Four: 4, Five: 5, Six: 6, Seven: 7, Eight: 8, Nine: 9 },
    StatusBarAlignment: { Left: 1, Right: 2 },
    ExtensionMode: { Production: 1, Development: 2, Test: 3 },
    UIKind: { Desktop: 1, Web: 2 },
    LogLevel: { Off: 0, Trace: 1, Debug: 2, Info: 3, Warning: 4, Error: 5 },
    ConfigurationTarget: { Global: 1, Workspace: 2, WorkspaceFolder: 3 },
    FileType: { Unknown: 0, File: 1, Directory: 2, SymbolicLink: 64 },
    FileChangeType: { Changed: 1, Created: 2, Deleted: 3 },
    TextEditorRevealType: { Default: 0, InCenter: 1, InCenterIfOutsideViewport: 2, AtTop: 3 },
    TextEditorSelectionChangeKind: { Keyboard: 1, Mouse: 2, Command: 3 },
    OverviewRulerLane: { Left: 1, Center: 2, Right: 4, Full: 7 },
    DecorationRangeBehavior: { OpenOpen: 0, ClosedClosed: 1, OpenClosed: 2, ClosedOpen: 3 },
    FoldingRangeKind: { Comment: 1, Imports: 2, Region: 3 },
    CommentThreadCollapsibleState: { Collapsed: 0, Expanded: 1 },
    CommentMode: { Editing: 0, Preview: 1 },
    QuickInputButtons: { Back: { iconPath: new ThemeIcon('arrow-left') } },
    InputBoxValidationSeverity: { Error: 0, Warning: 1, Info: 2 },
    ProgressLocation: { SourceControl: 1, Window: 10, Notification: 15 },
    TerminalExitReason: { Unknown: 0, Shutdown: 1, Process: 2, User: 3, Extension: 4 },
    TerminalLocation: { Panel: 1, Editor: 2 },
    Uri: {
      file: (path) => ({ scheme: 'file', path, fsPath: path, toString: () => 'file://' + path, with: (change) => vscode.Uri.file(change.path || path) }),
      parse: (value) => ({ scheme: 'file', path: value, fsPath: value, toString: () => value }),
      joinPath: (base, ...parts) => vscode.Uri.file([base.path, ...parts].join('/')),
    },
    version: '1.85.0',
    workspace: {
      workspaceFolders: _workspaceFolders,
      getConfiguration: (section) => ({
        get: (key, defaultValue) => defaultValue,
        update: () => Promise.resolve(),
        has: () => false,
        inspect: () => undefined
      }),
      onDidChangeWorkspaceFolders: () => ({ dispose: () => {} }),
      onDidSaveTextDocument: () => ({ dispose: () => {} }),
      onDidChangeTextDocument: () => ({ dispose: () => {} }),
      onDidOpenTextDocument: () => ({ dispose: () => {} }),
      onDidCloseTextDocument: () => ({ dispose: () => {} }),
      applyEdit: () => Promise.resolve(true),
      openTextDocument: (uri) => Promise.resolve({
        uri, getText: () => '', lineCount: 0, languageId: 'plaintext',
        version: 1, isDirty: false, isUntitled: false, fileName: String(uri), eol: 1,
        positionAt: () => new Position(0, 0), offsetAt: () => 0,
      }),
      fs: {
        readFile: () => Promise.resolve(new Uint8Array(0)),
        writeFile: () => Promise.resolve(),
        stat: () => Promise.reject(new Error('ENOENT')),
        delete: () => Promise.resolve(),
        createDirectory: () => Promise.resolve(),
      },
      findFiles: () => Promise.resolve([]),
      asRelativePath: (p) => p,
      saveAll: () => Promise.resolve(false),
      onWillSaveTextDocument: () => ({ dispose: () => {} }),
      onDidCreateFiles: () => ({ dispose: () => {} }),
      onDidDeleteFiles: () => ({ dispose: () => {} }),
      onDidRenameFiles: () => ({ dispose: () => {} }),
      onWillCreateFiles: () => ({ dispose: () => {} }),
      onWillDeleteFiles: () => ({ dispose: () => {} }),
      onWillRenameFiles: () => ({ dispose: () => {} }),
    },
    window: {
      activeTextEditor: undefined,
      visibleTextEditors: _visibleTextEditors,
      terminals: _terminals,
      activeTerminal: undefined,
      showInformationMessage: () => Promise.resolve(),
      showWarningMessage: () => Promise.resolve(),
      showErrorMessage: () => Promise.resolve(),
      showInputBox: () => Promise.resolve(''),
      showQuickPick: () => Promise.resolve(undefined),
      showOpenDialog: () => Promise.resolve(undefined),
      showSaveDialog: () => Promise.resolve(undefined),
      createOutputChannel: (name) => ({
        name, append: () => {}, appendLine: () => {}, clear: () => {},
        show: () => {}, hide: () => {}, dispose: () => {},
      }),
      createTerminal: (opts) => ({
        name: opts?.name || 'terminal', sendText: () => {}, show: () => {},
        hide: () => {}, dispose: () => {},
      }),
      createWebviewPanel: (viewType, title, showOptions, options) => ({
        viewType, title,
        webview: { html: '', postMessage: () => Promise.resolve(true), onDidReceiveMessage: () => ({ dispose: () => {} }), asWebviewUri: (uri) => uri },
        reveal: () => {}, dispose: () => {},
        onDidDispose: () => ({ dispose: () => {} }),
        onDidChangeViewState: () => ({ dispose: () => {} }),
      }),
      withProgress: (opts, task) => task({ report: () => {} }),
      setStatusBarMessage: () => ({ dispose: () => {} }),
      registerTreeDataProvider: () => ({ dispose: () => {} }),
      createTreeView: () => ({ dispose: () => {}, onDidChangeSelection: () => ({ dispose: () => {} }), onDidChangeVisibility: () => ({ dispose: () => {} }), reveal: () => Promise.resolve() }),
      onDidChangeActiveTextEditor: () => ({ dispose: () => {} }),
      onDidChangeVisibleTextEditors: () => ({ dispose: () => {} }),
      onDidChangeTextEditorSelection: () => ({ dispose: () => {} }),
      onDidChangeTextEditorVisibleRanges: () => ({ dispose: () => {} }),
      onDidOpenTerminal: () => ({ dispose: () => {} }),
      onDidCloseTerminal: () => ({ dispose: () => {} }),
      onDidChangeTerminalState: () => ({ dispose: () => {} }),
      registerUriHandler: () => ({ dispose: () => {} }),
      registerWebviewViewProvider: () => ({ dispose: () => {} }),
      registerCustomEditorProvider: () => ({ dispose: () => {} }),
      registerTerminalLinkProvider: () => ({ dispose: () => {} }),
      registerTerminalProfileProvider: () => ({ dispose: () => {} }),
      registerTerminalQuickFixProvider: () => ({ dispose: () => {} }),
      registerTerminalCompletionProvider: () => ({ dispose: () => {} }),
      registerTerminalActionProvider: () => ({ dispose: () => {} }),
      registerTerminalIconProvider: () => ({ dispose: () => {} }),
      registerTerminalDecorationProvider: () => ({ dispose: () => {} }),
      registerTerminalShellIntegrationProvider: () => ({ dispose: () => {} }),
    },
    commands: {
      registerCommand: (name, handler) => { _commands.set(name, handler); return { dispose: () => _commands.delete(name) }; },
      executeCommand: (name, ...args) => { const handler = _commands.get(name); if (handler) return Promise.resolve(handler(...args)); return Promise.resolve(undefined); },
      getCommands: () => Promise.resolve([..._commands.keys()]),
      registerTextEditorCommand: (name, handler) => { _commands.set(name, handler); return { dispose: () => _commands.delete(name) }; },
    },
    languages: {
      getDiagnostics: () => _diagnostics,
      getDiagnosticsForUri: () => [],
      createDiagnosticCollection: (name) => ({
        name, set: () => {}, delete: () => {}, clear: () => {}, dispose: () => {},
        forEach: () => {}, get: () => undefined, has: () => false,
      }),
      registerCompletionItemProvider: () => ({ dispose: () => {} }),
      registerHoverProvider: () => ({ dispose: () => {} }),
      registerSignatureHelpProvider: () => ({ dispose: () => {} }),
      registerDefinitionProvider: () => ({ dispose: () => {} }),
      registerReferenceProvider: () => ({ dispose: () => {} }),
      registerDocumentHighlightProvider: () => ({ dispose: () => {} }),
      registerDocumentSymbolProvider: () => ({ dispose: () => {} }),
      registerWorkspaceSymbolProvider: () => ({ dispose: () => {} }),
      registerCodeActionsProvider: () => ({ dispose: () => {} }),
      registerCodeLensProvider: () => ({ dispose: () => {} }),
      registerDocumentFormattingEditProvider: () => ({ dispose: () => {} }),
      registerDocumentRangeFormattingEditProvider: () => ({ dispose: () => {} }),
      registerOnTypeFormattingEditProvider: () => ({ dispose: () => {} }),
      registerRenameProvider: () => ({ dispose: () => {} }),
      registerDocumentLinkProvider: () => ({ dispose: () => {} }),
      registerColorProvider: () => ({ dispose: () => {} }),
      registerFoldingRangeProvider: () => ({ dispose: () => {} }),
      registerDeclarationProvider: () => ({ dispose: () => {} }),
      registerImplementationProvider: () => ({ dispose: () => {} }),
      registerTypeDefinitionProvider: () => ({ dispose: () => {} }),
      registerEvaluatableExpressionProvider: () => ({ dispose: () => {} }),
      registerInlineValuesProvider: () => ({ dispose: () => {} }),
      registerDocumentDropEditProvider: () => ({ dispose: () => {} }),
      registerDocumentPasteEditProvider: () => ({ dispose: () => {} }),
      registerDocumentSemanticTokensProvider: () => ({ dispose: () => {} }),
      registerDocumentRangeSemanticTokensProvider: () => ({ dispose: () => {} }),
      registerLinkedEditingRangeProvider: () => ({ dispose: () => {} }),
      registerTypeHierarchyProvider: () => ({ dispose: () => {} }),
      registerCallHierarchyProvider: () => ({ dispose: () => {} }),
      registerInlayHintsProvider: () => ({ dispose: () => {} }),
      registerInlineCompletionItemProvider: () => ({ dispose: () => {} }),
      match: () => 0,
      getLanguages: () => Promise.resolve([]),
      setTextDocumentLanguage: () => Promise.resolve({}),
      registerDocumentEditProvider: () => ({ dispose: () => {} }),
    },
    debug: {
      activeDebugSession: undefined,
      breakpoints: _breakpoints,
      onDidStartDebugSession: () => ({ dispose: () => {} }),
      onDidTerminateDebugSession: () => ({ dispose: () => {} }),
      onDidChangeActiveDebugSession: () => ({ dispose: () => {} }),
      onDidReceiveDebugSessionCustomEvent: () => ({ dispose: () => {} }),
      onDidChangeBreakpoints: () => ({ dispose: () => {} }),
      startDebugging: () => Promise.resolve(true),
      stopDebugging: () => Promise.resolve(),
      addBreakpoints: () => {},
      removeBreakpoints: () => {},
      registerDebugConfigurationProvider: () => ({ dispose: () => {} }),
      registerDebugAdapterDescriptorFactory: () => ({ dispose: () => {} }),
      registerDebugAdapterTrackerFactory: () => ({ dispose: () => {} }),
      registerDebugConsoleModeProvider: () => ({ dispose: () => {} }),
    },
    tasks: {
      fetchTasks: () => Promise.resolve([]),
      executeTask: () => Promise.resolve({}),
      onDidStartTask: () => ({ dispose: () => {} }),
      onDidEndTask: () => ({ dispose: () => {} }),
      onDidStartTaskProcess: () => ({ dispose: () => {} }),
      onDidEndTaskProcess: () => ({ dispose: () => {} }),
      registerTaskProvider: () => ({ dispose: () => {} }),
    },
    tests: {
      createTestController: (id, label) => new TestController(id, label),
      createTestRunProfile: () => ({ dispose: () => {} }),
      onDidChangeTestResults: () => ({ dispose: () => {} }),
      registerTestController: () => ({ dispose: () => {} }),
    },
    extensions: {
      getExtension: () => undefined,
      all: [],
      onDidChangeExtensions: () => ({ dispose: () => {} }),
    },
    env: {
      appName: 'VSCODER://BRIDGE', appRoot: '', language: 'en', uriScheme: 'vscode',
      clipboard: { readText: () => Promise.resolve(''), writeText: () => Promise.resolve() },
      openExternal: () => Promise.resolve(true),
      asExternalUri: (uri) => Promise.resolve(uri),
      remoteName: undefined, remoteAuthority: undefined, uiKind: 1,
      sessionId: '', machineId: '', sessionName: '', logLevel: 0,
      onDidChangeLogLevel: () => ({ dispose: () => {} }),
      isNewAppInstall: false, isTelemetryEnabled: true,
      onDidChangeTelemetryEnabled: () => ({ dispose: () => {} }),
      telemetryConfiguration: {},
      onDidChangeTelemetryConfiguration: () => ({ dispose: () => {} }),
      isExtensionDevelopment: false, extensionMode: 1,
      env: {}, shell: '',
      onDidChangeShell: () => ({ dispose: () => {} }),
    },
  };

  globalThis.vscode = vscode;
})();
