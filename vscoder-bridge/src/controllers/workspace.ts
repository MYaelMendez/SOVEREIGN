/**
 * VSCODER://BRIDGE — Workspace Controller
 * Full workspace control: folders, files, search, configuration.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export interface WorkspaceInfo {
  folders: Array<{ name: string; path: string; index: number }>;
  name: string;
  isTrusted: boolean;
  rootPath: string;
}

export interface FileEntry {
  name: string;
  path: string;
  isDirectory: boolean;
  size: number;
  children?: FileEntry[];
}

export class WorkspaceController {
  getInfo(): WorkspaceInfo {
    const folders = vscode.workspace.workspaceFolders || [];
    return {
      folders: folders.map((f, i) => ({
        name: f.name,
        path: f.uri.fsPath,
        index: i,
      })),
      name: folders[0]?.name || '',
      isTrusted: true,
      rootPath: folders[0]?.uri.fsPath || '',
    };
  }

  async listFiles(dirPath: string, maxDepth: number = 3): Promise<FileEntry[]> {
    const entries: FileEntry[] = [];
    try {
      const items = fs.readdirSync(dirPath, { withFileTypes: true });
      for (const item of items) {
        if (item.name.startsWith('.') || item.name === 'node_modules') continue;
        const fullPath = path.join(dirPath, item.name);
        const entry: FileEntry = {
          name: item.name,
          path: fullPath,
          isDirectory: item.isDirectory(),
          size: 0,
        };
        if (item.isDirectory() && maxDepth > 0) {
          entry.children = await this.listFiles(fullPath, maxDepth - 1);
        } else if (item.isFile()) {
          try {
            entry.size = fs.statSync(fullPath).size;
          } catch { /* ignore */ }
        }
        entries.push(entry);
      }
    } catch {
      // Directory not accessible
    }
    return entries;
  }

  async readFile(filePath: string): Promise<string> {
    try {
      return fs.readFileSync(filePath, 'utf8');
    } catch (e: unknown) {
      throw new Error(`Failed to read ${filePath}: ${(e instanceof Error ? e.message : String(e))}`);
    }
  }

  async writeFile(filePath: string, content: string): Promise<void> {
    try {
      const dir = path.dirname(filePath);
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(filePath, content, 'utf8');
    } catch (e: unknown) {
      throw new Error(`Failed to write ${filePath}: ${(e instanceof Error ? e.message : String(e))}`);
    }
  }

  async searchFiles(pattern: string, exclude: string = '**/node_modules/**'): Promise<string[]> {
    const files = await vscode.workspace.findFiles(pattern, exclude, 100);
    return files.map(f => f.fsPath);
  }

  getConfiguration<T>(section: string, key: string, defaultValue: T): T {
    const config = vscode.workspace.getConfiguration(section);
    return config.get<T>(key, defaultValue);
  }

  async openFolder(folderPath: string): Promise<void> {
    await vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(folderPath), true);
  }

  async createTerminal(name: string, cwd?: string): Promise<vscode.Terminal> {
    const terminal = vscode.window.createTerminal({ name, cwd });
    terminal.show();
    return terminal;
  }

  async executeCommand(command: string, ...args: unknown[]): Promise<any> {
    return vscode.commands.executeCommand(command, ...args);
  }
}
