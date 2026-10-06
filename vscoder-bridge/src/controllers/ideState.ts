/**
 * VSCODER://BRIDGE — IDE State Observer (VSCODER_IDE_STATE_V1)
 *
 * Observes and broadcasts IDE state:
 *   workspace, active_file, open_editors, cursor, selection, visible_ranges,
 *   diagnostics, terminals, running_tasks, tests, debug_session,
 *   breakpoints, scm_state, current_branch, dirty_files, active_panel,
 *   focused_view
 *
 * Event-driven shared state with human in the loop.
 */

import * as vscode from 'vscode';
import * as crypto from 'crypto';

export interface IDEStateV1 {
  version: 'VSCODER_IDE_STATE_V1';
  timestamp: string;
  workspace: {
    folders: string[];
    name: string;
    isTrusted: boolean;
  };
  active_file: {
    path: string;
    language: string;
    isDirty: boolean;
    isUntitled: boolean;
    scheme: string;
  } | null;
  open_editors: Array<{
    path: string;
    language: string;
    isDirty: boolean;
    viewColumn: number;
  }>;
  cursor: {
    file: string;
    line: number;
    character: number;
  } | null;
  selection: {
    file: string;
    start: { line: number; character: number };
    end: { line: number; character: number };
    isEmpty: boolean;
  } | null;
  visible_ranges: Array<{
    file: string;
    start: { line: number; character: number };
    end: { line: number; character: number };
  }>;
  diagnostics: Array<{
    file: string;
    message: string;
    severity: string;
    line: number;
    source?: string;
  }>;
  terminals: Array<{
    name: string;
    isBusy: boolean;
  }>;
  running_tasks: Array<{
    name: string;
    source: string;
  }>;
  tests: {
    controllers: number;
    totalTests: number;
  };
  debug_session: {
    isActive: boolean;
    sessionId?: string;
    sessionType?: string;
    sessionName?: string;
  };
  breakpoints: Array<{
    file: string;
    line: number;
    enabled: boolean;
    condition?: string;
  }>;
  scm_state: {
    branch: string;
    changes: number;
    repositories: number;
  };
  current_branch: string;
  dirty_files: string[];
  active_panel: string | null;
  focused_view: string | null;
}

export class IDEStateObserver {
  private _state: IDEStateV1;
  private _onDidChangeState = new vscode.EventEmitter<IDEStateV1>();
  public readonly onDidChangeState = this._onDidChangeState.event;
  private _disposables: vscode.Disposable[] = [];
  private _autoObserve: boolean;

  constructor(autoObserve: boolean = true) {
    this._autoObserve = autoObserve;
    this._state = this.captureState();
    if (autoObserve) {
      this.startObserving();
    }
  }

  get state(): IDEStateV1 {
    return this._state;
  }

  captureState(): IDEStateV1 {
    const workspaceFolders = vscode.workspace.workspaceFolders || [];
    const activeEditor = vscode.window.activeTextEditor;
    const visibleEditors = vscode.window.visibleTextEditors;
    const terminals = vscode.window.terminals;
    const debugSession = vscode.debug.activeDebugSession;
    const breakpoints = vscode.debug.breakpoints;

    const openEditors = visibleEditors.map(e => ({
      path: e.document.uri.fsPath,
      language: e.document.languageId,
      isDirty: e.document.isDirty,
      viewColumn: e.viewColumn || 0,
    }));

    const cursor = activeEditor ? {
      file: activeEditor.document.uri.fsPath,
      line: activeEditor.selection.active.line,
      character: activeEditor.selection.active.character,
    } : null;

    const selection = activeEditor ? {
      file: activeEditor.document.uri.fsPath,
      start: {
        line: activeEditor.selection.start.line,
        character: activeEditor.selection.start.character,
      },
      end: {
        line: activeEditor.selection.end.line,
        character: activeEditor.selection.end.character,
      },
      isEmpty: activeEditor.selection.isEmpty,
    } : null;

    const visibleRanges = visibleEditors.map(e => ({
      file: e.document.uri.fsPath,
      start: {
        line: e.visibleRanges[0]?.start.line || 0,
        character: e.visibleRanges[0]?.start.character || 0,
      },
      end: {
        line: e.visibleRanges[0]?.end.line || 0,
        character: e.visibleRanges[0]?.end.character || 0,
      },
    }));

    const allDiagnostics = vscode.languages.getDiagnostics();
    const diagnostics: IDEStateV1['diagnostics'] = [];
    for (const [uri, diags] of allDiagnostics) {
      for (const d of diags) {
        diagnostics.push({
          file: uri.fsPath,
          message: d.message,
          severity: this.severityToString(d.severity),
          line: d.range.start.line,
          source: d.source,
        });
      }
    }

    const dirtyFiles = visibleEditors
      .filter(e => e.document.isDirty)
      .map(e => e.document.uri.fsPath);

    const gitExt = vscode.extensions.getExtension('vscode.git');
    let branch = 'unknown';
    let changes = 0;
    let repos = 0;
    if (gitExt) {
      const api = (gitExt.exports as any)?.getAPI?.(1);
      if (api) {
        repos = api.repositories?.length || 0;
        const repo = api.repositories?.[0];
        if (repo) {
          branch = repo.state?.HEAD?.name || 'unknown';
          changes = (repo.state?.workingTreeChanges?.length || 0)
            + (repo.state?.indexChanges?.length || 0)
            + (repo.state?.mergeChanges?.length || 0);
        }
      }
    }

    const activePanel = vscode.window.activeTerminal ? 'terminal' : null;

    const state: IDEStateV1 = {
      version: 'VSCODER_IDE_STATE_V1',
      timestamp: new Date().toISOString(),
      workspace: {
        folders: workspaceFolders.map(f => f.uri.fsPath),
        name: workspaceFolders[0]?.name || '',
        isTrusted: true,
      },
      active_file: activeEditor ? {
        path: activeEditor.document.uri.fsPath,
        language: activeEditor.document.languageId,
        isDirty: activeEditor.document.isDirty,
        isUntitled: activeEditor.document.isUntitled,
        scheme: activeEditor.document.uri.scheme,
      } : null,
      open_editors: openEditors,
      cursor,
      selection,
      visible_ranges: visibleRanges,
      diagnostics,
      terminals: terminals.map(t => ({
        name: t.name,
        isBusy: false,
      })),
      running_tasks: [],
      tests: {
        controllers: 0,
        totalTests: 0,
      },
      debug_session: {
        isActive: debugSession !== undefined,
        sessionId: debugSession?.id,
        sessionType: debugSession?.type,
        sessionName: debugSession?.name,
      },
      breakpoints: breakpoints.map(b => ({
        file: (b as any)?.location?.uri?.fsPath || '',
        line: (b as any)?.location?.range?.start?.line || 0,
        enabled: b.enabled,
        condition: (b as any)?.condition,
      })),
      scm_state: {
        branch,
        changes,
        repositories: repos,
      },
      current_branch: branch,
      dirty_files: dirtyFiles,
      active_panel: activePanel,
      focused_view: null,
    };

    return state;
  }

  refresh(): IDEStateV1 {
    this._state = this.captureState();
    this._onDidChangeState.fire(this._state);
    return this._state;
  }

  startObserving(): void {
    this._disposables.push(
      vscode.window.onDidChangeActiveTextEditor(() => this.refresh()),
      vscode.window.onDidChangeVisibleTextEditors(() => this.refresh()),
      vscode.window.onDidChangeTextEditorSelection(() => this.refresh()),
      vscode.window.onDidChangeTextEditorVisibleRanges(() => this.refresh()),
      vscode.workspace.onDidChangeTextDocument(() => this.refresh()),
      vscode.workspace.onDidSaveTextDocument(() => this.refresh()),
      vscode.workspace.onDidOpenTextDocument(() => this.refresh()),
      vscode.workspace.onDidCloseTextDocument(() => this.refresh()),
      vscode.debug.onDidStartDebugSession(() => this.refresh()),
      vscode.debug.onDidTerminateDebugSession(() => this.refresh()),
      vscode.debug.onDidChangeBreakpoints(() => this.refresh()),
      vscode.tasks.onDidStartTask(() => this.refresh()),
      vscode.tasks.onDidEndTask(() => this.refresh()),
    );
  }

  dispose(): void {
    this._disposables.forEach(d => d.dispose());
    this._onDidChangeState.dispose();
  }

  private severityToString(severity: vscode.DiagnosticSeverity): string {
    const severities: Record<number, string> = {
      [vscode.DiagnosticSeverity.Error]: 'Error',
      [vscode.DiagnosticSeverity.Warning]: 'Warning',
      [vscode.DiagnosticSeverity.Information]: 'Information',
      [vscode.DiagnosticSeverity.Hint]: 'Hint',
    };
    return severities[severity] ?? 'Unknown';
  }
}
