/**
 * VSCODER://BRIDGE — UI Controller
 * UI control: panels, webviews, quick picks, input boxes, status bar.
 */

import * as vscode from 'vscode';

export class UIController {
  async showInformation(message: string): Promise<void> {
    await vscode.window.showInformationMessage(message);
  }

  async showWarning(message: string): Promise<void> {
    await vscode.window.showWarningMessage(message);
  }

  async showError(message: string): Promise<void> {
    await vscode.window.showErrorMessage(message);
  }

  async showInput(placeHolder: string, value?: string): Promise<string | undefined> {
    return vscode.window.showInputBox({ placeHolder, value });
  }

  async showQuickPick(items: string[], placeHolder?: string): Promise<string | undefined> {
    return vscode.window.showQuickPick(items, { placeHolder });
  }

  async showQuickPickItems(items: Array<{ label: string; description?: string; detail?: string }>, placeHolder?: string): Promise<{ label: string; description?: string; detail?: string } | undefined> {
    return vscode.window.showQuickPick(items, { placeHolder, matchOnDescription: true, matchOnDetail: true });
  }

  async showOpenDialog(options?: {
    canSelectFiles?: boolean;
    canSelectFolders?: boolean;
    canSelectMany?: boolean;
    filters?: Record<string, string[]>;
    defaultUri?: string;
    openLabel?: string;
  }): Promise<vscode.Uri[] | undefined> {
    const opts: vscode.OpenDialogOptions = {
      canSelectFiles: options?.canSelectFiles ?? true,
      canSelectFolders: options?.canSelectFolders ?? false,
      canSelectMany: options?.canSelectMany ?? false,
      filters: options?.filters,
      defaultUri: options?.defaultUri ? vscode.Uri.file(options.defaultUri) : undefined,
      openLabel: options?.openLabel,
    };
    return vscode.window.showOpenDialog(opts);
  }

  async showSaveDialog(options?: {
    filters?: Record<string, string[]>;
    defaultUri?: string;
    saveLabel?: string;
  }): Promise<vscode.Uri | undefined> {
    const opts: vscode.SaveDialogOptions = {
      filters: options?.filters,
      defaultUri: options?.defaultUri ? vscode.Uri.file(options.defaultUri) : undefined,
      saveLabel: options?.saveLabel,
    };
    return vscode.window.showSaveDialog(opts);
  }

  createOutputChannel(name: string): vscode.OutputChannel {
    return vscode.window.createOutputChannel(name);
  }

  createWebviewPanel(viewType: string, title: string, showOptions?: any, options?: vscode.WebviewPanelOptions): vscode.WebviewPanel {
    return vscode.window.createWebviewPanel(viewType, title, showOptions, options);
  }

  async withProgress<T>(title: string, task: (progress: vscode.Progress<{ message?: string; incremented?: number }>, token: vscode.CancellationToken) => Thenable<T>): Promise<T> {
    return vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title, cancellable: false },
      task
    );
  }

  setStatusBarMessage(text: string): vscode.Disposable {
    return vscode.window.setStatusBarMessage(text);
  }

  async createTreeView<T>(viewId: string, options: vscode.TreeViewOptions<T>): Promise<vscode.TreeView<T>> {
    return vscode.window.createTreeView(viewId, options);
  }

  registerTreeDataProvider<T>(viewId: string, treeDataProvider: vscode.TreeDataProvider<T>): vscode.Disposable {
    return vscode.window.registerTreeDataProvider(viewId, treeDataProvider);
  }

  registerUriHandler(handler: vscode.UriHandler): vscode.Disposable {
    return vscode.window.registerUriHandler(handler);
  }

  registerWebviewViewProvider(viewId: string, provider: vscode.WebviewViewProvider, options?: { webviewOptions?: { retainContextWhenHidden?: boolean } }): vscode.Disposable {
    return vscode.window.registerWebviewViewProvider(viewId, provider, options);
  }

  registerCustomEditorProvider(viewType: string, provider: vscode.CustomTextEditorProvider | vscode.CustomReadonlyEditorProvider, options?: { webviewOptions?: vscode.WebviewPanelOptions; supportsMultipleEditorsPerDocument?: boolean }): vscode.Disposable {
    return vscode.window.registerCustomEditorProvider(viewType, provider, options as any);
  }

  registerTerminalLinkProvider(provider: vscode.TerminalLinkProvider): vscode.Disposable {
    return vscode.window.registerTerminalLinkProvider(provider);
  }

  registerTerminalProfileProvider(provider: vscode.TerminalProfileProvider): vscode.Disposable {
    return (vscode.window as any).registerTerminalProfileProvider(provider);
  }

  // Note: registerTerminalQuickFixProvider, registerTerminalCompletionProvider,
  // registerTerminalActionProvider, registerTerminalIconProvider,
  // registerTerminalDecorationProvider, registerTerminalShellIntegrationProvider
  // are newer VS Code APIs not available in @types/vscode 1.85.0.
  // They are available at runtime in VS Code 1.87+.
}
