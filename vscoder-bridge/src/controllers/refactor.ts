/**
 * VSCODER://BRIDGE — Refactor Controller
 * LSP-based refactoring: rename, extract, move, code actions, organize imports.
 */

import * as vscode from 'vscode';

export interface RefactorAction {
  title: string;
  kind: string;
  isPreferred: boolean;
  hasEdit: boolean;
}

export interface RefactorResult {
  applied: boolean;
  title: string;
  editCount: number;
}

export class RefactorController {
  async listActions(filePath: string, range: { start: { line: number; character: number }; end: { line: number; character: number } }): Promise<RefactorAction[]> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const r = new vscode.Range(
      range.start.line, range.start.character,
      range.end.line, range.end.character
    );
    const actions = await vscode.commands.executeCommand<vscode.CodeAction[]>(
      'vscode.executeCodeActionProvider', doc.uri, r
    );
    return (actions || []).map(a => ({
      title: a.title,
      kind: a.kind?.value || '',
      isPreferred: a.isPreferred || false,
      hasEdit: a.edit !== undefined,
    }));
  }

  async applyAction(filePath: string, range: { start: { line: number; character: number }; end: { line: number; character: number } }, title: string): Promise<RefactorResult> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const r = new vscode.Range(
      range.start.line, range.start.character,
      range.end.line, range.end.character
    );
    const actions = await vscode.commands.executeCommand<vscode.CodeAction[]>(
      'vscode.executeCodeActionProvider', doc.uri, r
    );
    const match = (actions || []).find(a => a.title === title);
    if (!match) {
      return { applied: false, title, editCount: 0 };
    }
    if (match.edit) {
      const ok = await vscode.workspace.applyEdit(match.edit);
      return { applied: ok, title, editCount: match.edit.size };
    }
    return { applied: true, title, editCount: 0 };
  }

  async extractMethod(filePath: string, range: { start: { line: number; character: number }; end: { line: number; character: number } }): Promise<RefactorAction[]> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const r = new vscode.Range(
      range.start.line, range.start.character,
      range.end.line, range.end.character
    );
    const actions = await vscode.commands.executeCommand<vscode.CodeAction[]>(
      'vscode.executeCodeActionProvider', doc.uri, r, vscode.CodeActionKind.RefactorExtract
    );
    return (actions || []).map(a => ({
      title: a.title,
      kind: a.kind?.value || '',
      isPreferred: a.isPreferred || false,
      hasEdit: a.edit !== undefined,
    }));
  }

  async moveSymbol(filePath: string, range: { start: { line: number; character: number }; end: { line: number; character: number } }): Promise<RefactorAction[]> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const r = new vscode.Range(
      range.start.line, range.start.character,
      range.end.line, range.end.character
    );
    const actions = await vscode.commands.executeCommand<vscode.CodeAction[]>(
      'vscode.executeCodeActionProvider', doc.uri, r, vscode.CodeActionKind.RefactorMove
    );
    return (actions || []).map(a => ({
      title: a.title,
      kind: a.kind?.value || '',
      isPreferred: a.isPreferred || false,
      hasEdit: a.edit !== undefined,
    }));
  }

  async rewrite(filePath: string, range: { start: { line: number; character: number }; end: { line: number; character: number } }): Promise<RefactorAction[]> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const r = new vscode.Range(
      range.start.line, range.start.character,
      range.end.line, range.end.character
    );
    const actions = await vscode.commands.executeCommand<vscode.CodeAction[]>(
      'vscode.executeCodeActionProvider', doc.uri, r, vscode.CodeActionKind.RefactorRewrite
    );
    return (actions || []).map(a => ({
      title: a.title,
      kind: a.kind?.value || '',
      isPreferred: a.isPreferred || false,
      hasEdit: a.edit !== undefined,
    }));
  }

  async organizeImports(filePath: string): Promise<RefactorResult> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const fullRange = new vscode.Range(
      doc.positionAt(0),
      doc.positionAt(doc.getText().length)
    );
    const actions = await vscode.commands.executeCommand<vscode.CodeAction[]>(
      'vscode.executeCodeActionProvider', doc.uri, fullRange, vscode.CodeActionKind.SourceOrganizeImports
    );
    if (!actions || actions.length === 0) {
      return { applied: false, title: '(organize imports)', editCount: 0 };
    }
    const target = actions[0];
    if (target.edit) {
      const ok = await vscode.workspace.applyEdit(target.edit);
      return { applied: ok, title: target.title, editCount: target.edit.size };
    }
    return { applied: true, title: target.title, editCount: 0 };
  }

  async rename(filePath: string, position: { line: number; character: number }, newName: string): Promise<boolean> {
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

  async findReferences(filePath: string, position: { line: number; character: number }): Promise<vscode.Location[]> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const pos = new vscode.Position(position.line, position.character);
    const locations = await vscode.commands.executeCommand<vscode.Location[]>(
      'vscode.executeReferenceProvider', doc.uri, pos, { includeDeclaration: true }
    );
    return locations || [];
  }

  async findDefinition(filePath: string, position: { line: number; character: number }): Promise<vscode.Location[]> {
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
    const pos = new vscode.Position(position.line, position.character);
    const locations = await vscode.commands.executeCommand<vscode.Location[]>(
      'vscode.executeDefinitionProvider', doc.uri, pos
    );
    return locations || [];
  }
}
