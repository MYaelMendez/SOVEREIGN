/**
 * VSCODER://BRIDGE — Editor Controller
 * Full editor control: open, close, edit, navigate, selection, formatting.
 */

import * as vscode from 'vscode';

export interface EditorInfo {
  path: string;
  language: string;
  isDirty: boolean;
  isUntitled: boolean;
  viewColumn: number;
  lineCount: number;
  cursor: { line: number; character: number };
  selection: {
    start: { line: number; character: number };
    end: { line: number; character: number };
    isEmpty: boolean;
  };
}

export interface TextEdit {
  range: { start: { line: number; character: number }; end: { line: number; character: number } };
  newText: string;
}

export class EditorController {
  getActiveEditor(): EditorInfo | null {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return null;
    return this.editorToInfo(editor);
  }

  getVisibleEditors(): EditorInfo[] {
    return vscode.window.visibleTextEditors.map(e => this.editorToInfo(e));
  }

  async openFile(filePath: string, viewColumn?: vscode.ViewColumn): Promise<EditorInfo> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const editor = await vscode.window.showTextDocument(doc, viewColumn);
    return this.editorToInfo(editor);
  }

  async closeFile(filePath: string): Promise<void> {
    const editor = vscode.window.visibleTextEditors.find(
      e => e.document.uri.fsPath === filePath
    );
    if (editor) {
      await vscode.window.showTextDocument(editor.document);
      await vscode.commands.executeCommand('workbench.action.closeActiveEditor');
    }
  }

  async applyEdits(filePath: string, edits: TextEdit[]): Promise<boolean> {
    const editor = vscode.window.visibleTextEditors.find(
      e => e.document.uri.fsPath === filePath
    );
    if (!editor) {
      const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
      const ed = await vscode.window.showTextDocument(doc);
      return this.applyEditsToEditor(ed, edits);
    }
    return this.applyEditsToEditor(editor, edits);
  }

  private async applyEditsToEditor(editor: vscode.TextEditor, edits: TextEdit[]): Promise<boolean> {
    const workspaceEdit = new vscode.WorkspaceEdit();
    const uri = editor.document.uri;
    for (const edit of edits) {
      const range = new vscode.Range(
        edit.range.start.line, edit.range.start.character,
        edit.range.end.line, edit.range.end.character
      );
      workspaceEdit.replace(uri, range, edit.newText);
    }
    return vscode.workspace.applyEdit(workspaceEdit);
  }

  async insertText(filePath: string, position: { line: number; character: number }, text: string): Promise<boolean> {
    const editor = vscode.window.visibleTextEditors.find(
      e => e.document.uri.fsPath === filePath
    );
    if (!editor) return false;
    return editor.edit(editBuilder => {
      editBuilder.insert(new vscode.Position(position.line, position.character), text);
    });
  }

  async deleteRange(filePath: string, range: { start: { line: number; character: number }; end: { line: number; character: number } }): Promise<boolean> {
    const editor = vscode.window.visibleTextEditors.find(
      e => e.document.uri.fsPath === filePath
    );
    if (!editor) return false;
    return editor.edit(editBuilder => {
      const r = new vscode.Range(
        range.start.line, range.start.character,
        range.end.line, range.end.character
      );
      editBuilder.delete(r);
    });
  }

  async formatDocument(filePath: string): Promise<void> {
    const editor = vscode.window.visibleTextEditors.find(
      e => e.document.uri.fsPath === filePath
    );
    if (editor) {
      await vscode.commands.executeCommand('editor.action.formatDocument');
    }
  }

  async formatSelection(filePath: string): Promise<void> {
    const editor = vscode.window.visibleTextEditors.find(
      e => e.document.uri.fsPath === filePath
    );
    if (editor) {
      await vscode.commands.executeCommand('editor.action.formatSelection');
    }
  }

  async goToDefinition(filePath: string, position: { line: number; character: number }): Promise<vscode.Location[]> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const pos = new vscode.Position(position.line, position.character);
    const locations = await vscode.commands.executeCommand<vscode.Location[]>(
      'vscode.executeDefinitionProvider', doc.uri, pos
    );
    return locations || [];
  }

  async findReferences(filePath: string, position: { line: number; character: number }): Promise<vscode.Location[]> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const pos = new vscode.Position(position.line, position.character);
    const locations = await vscode.commands.executeCommand<vscode.Location[]>(
      'vscode.executeReferenceProvider', doc.uri, pos, { includeDeclaration: true }
    );
    return locations || [];
  }

  async renameSymbol(filePath: string, position: { line: number; character: number }, newName: string): Promise<boolean> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const pos = new vscode.Position(position.line, position.character);
    const edit = await vscode.commands.executeCommand<vscode.WorkspaceEdit>(
      'vscode.executeRenameProvider', doc.uri, pos, newName
    );
    if (edit) {
      return vscode.workspace.applyEdit(edit);
    }
    return false;
  }

  async getDocumentSymbols(filePath: string): Promise<vscode.DocumentSymbol[]> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
      'vscode.executeDocumentSymbolProvider', doc.uri
    );
    return symbols || [];
  }

  async getWorkspaceSymbols(query: string): Promise<vscode.SymbolInformation[]> {
    const symbols = await vscode.commands.executeCommand<vscode.SymbolInformation[]>(
      'vscode.executeWorkspaceSymbolProvider', query
    );
    return symbols || [];
  }

  async getCodeActions(filePath: string, range: { start: { line: number; character: number }; end: { line: number; character: number } }): Promise<vscode.CodeAction[]> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const r = new vscode.Range(
      range.start.line, range.start.character,
      range.end.line, range.end.character
    );
    const actions = await vscode.commands.executeCommand<vscode.CodeAction[]>(
      'vscode.executeCodeActionProvider', doc.uri, r
    );
    return actions || [];
  }

  async getDiagnostics(filePath?: string): Promise<Array<{ file: string; message: string; severity: string; line: number }>> {
    if (filePath) {
      const diags = vscode.languages.getDiagnostics(vscode.Uri.file(filePath));
      return diags.map(d => ({
        file: filePath,
        message: d.message,
        severity: this.severityToString(d.severity),
        line: d.range.start.line,
      }));
    }
    const all = vscode.languages.getDiagnostics();
    const result: Array<{ file: string; message: string; severity: string; line: number }> = [];
    for (const [uri, diags] of all) {
      for (const d of diags) {
        result.push({
          file: uri.fsPath,
          message: d.message,
          severity: this.severityToString(d.severity),
          line: d.range.start.line,
        });
      }
    }
    return result;
  }

  private editorToInfo(editor: vscode.TextEditor): EditorInfo {
    return {
      path: editor.document.uri.fsPath,
      language: editor.document.languageId,
      isDirty: editor.document.isDirty,
      isUntitled: editor.document.isUntitled,
      viewColumn: editor.viewColumn || 0,
      lineCount: editor.document.lineCount,
      cursor: {
        line: editor.selection.active.line,
        character: editor.selection.active.character,
      },
      selection: {
        start: {
          line: editor.selection.start.line,
          character: editor.selection.start.character,
        },
        end: {
          line: editor.selection.end.line,
          character: editor.selection.end.character,
        },
        isEmpty: editor.selection.isEmpty,
      },
    };
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
