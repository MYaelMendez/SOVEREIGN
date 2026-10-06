/**
 * VSCODER://BRIDGE — SCM (Source Control Management) Controller
 * Git operations via VS Code's built-in git extension API.
 */

import * as vscode from 'vscode';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface SCMInfo {
  branch: string;
  changes: number;
  repositories: number;
  rootUri: string;
}

export interface SCMChange {
  path: string;
  status: string;
  uri: string;
}

export class SCMController {
  private getGitAPI(): any {
    const gitExt = vscode.extensions.getExtension('vscode.git');
    if (!gitExt) return undefined;
    return (gitExt.exports as any)?.getAPI?.(1);
  }

  getInfo(): SCMInfo {
    const api = this.getGitAPI();
    const repo = api?.repositories?.[0];
    return {
      branch: repo?.state?.HEAD?.name || 'unknown',
      changes: repo
        ? (repo.state?.workingTreeChanges?.length || 0)
          + (repo.state?.indexChanges?.length || 0)
          + (repo.state?.mergeChanges?.length || 0)
        : 0,
      repositories: api?.repositories?.length || 0,
      rootUri: repo?.rootUri?.fsPath || '',
    };
  }

  async getStatus(): Promise<SCMChange[]> {
    const api = this.getGitAPI();
    const repo = api?.repositories?.[0];
    if (!repo) return [];

    const changes: SCMChange[] = [];
    for (const c of repo.state?.workingTreeChanges || []) {
      changes.push({ path: c.uri.fsPath, status: 'modified', uri: c.uri.toString() });
    }
    for (const c of repo.state?.indexChanges || []) {
      changes.push({ path: c.uri.fsPath, status: 'staged', uri: c.uri.toString() });
    }
    for (const c of repo.state?.mergeChanges || []) {
      changes.push({ path: c.uri.fsPath, status: 'merge', uri: c.uri.toString() });
    }
    return changes;
  }

  async getDiff(): Promise<string> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    try {
      const { stdout } = await execAsync('git diff', { cwd: workspaceRoot, timeout: 10000 });
      return stdout;
    } catch (e: unknown) {
      return (e as Error & { stdout?: string }).stdout || (e instanceof Error ? e.message : String(e));
    }
  }

  async getDiffStat(): Promise<string> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    try {
      const { stdout } = await execAsync('git diff --stat', { cwd: workspaceRoot, timeout: 10000 });
      return stdout;
    } catch (e: unknown) {
      return (e as Error & { stdout?: string }).stdout || (e instanceof Error ? e.message : String(e));
    }
  }

  async getStatusShort(): Promise<string> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    try {
      const { stdout } = await execAsync('git status --short', { cwd: workspaceRoot, timeout: 10000 });
      return stdout;
    } catch (e: unknown) {
      return (e as Error & { stdout?: string }).stdout || (e instanceof Error ? e.message : String(e));
    }
  }

  async getLog(count: number = 10): Promise<string> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    try {
      const { stdout } = await execAsync(`git log --oneline -${count}`, { cwd: workspaceRoot, timeout: 10000 });
      return stdout;
    } catch (e: unknown) {
      return (e as Error & { stdout?: string }).stdout || (e instanceof Error ? e.message : String(e));
    }
  }

  async getBranches(): Promise<string[]> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    try {
      const { stdout } = await execAsync('git branch -a', { cwd: workspaceRoot, timeout: 10000 });
      return stdout.split('\n').filter(b => b.trim()).map(b => b.trim());
    } catch {
      return [];
    }
  }

  async checkout(branch: string): Promise<void> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    await execAsync(`git checkout ${branch}`, { cwd: workspaceRoot, timeout: 10000 });
  }

  async createBranch(branch: string): Promise<void> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    await execAsync(`git checkout -b ${branch}`, { cwd: workspaceRoot, timeout: 10000 });
  }

  async stage(files: string[]): Promise<void> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    for (const file of files) {
      await execAsync(`git add "${file}"`, { cwd: workspaceRoot, timeout: 10000 });
    }
  }

  async unstage(files: string[]): Promise<void> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    for (const file of files) {
      await execAsync(`git reset HEAD "${file}"`, { cwd: workspaceRoot, timeout: 10000 });
    }
  }

  async commit(message: string): Promise<void> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    await execAsync(`git commit -m "${message.replace(/"/g, '\\"')}"`, { cwd: workspaceRoot, timeout: 10000 });
  }

  async push(): Promise<void> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    await execAsync('git push', { cwd: workspaceRoot, timeout: 30000 });
  }

  async pull(): Promise<void> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    await execAsync('git pull', { cwd: workspaceRoot, timeout: 30000 });
  }

  async fetch(): Promise<void> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    await execAsync('git fetch', { cwd: workspaceRoot, timeout: 30000 });
  }

  async showDiff(filePath: string): Promise<void> {
    await vscode.commands.executeCommand('git.diff', vscode.Uri.file(filePath));
  }

  async refresh(): Promise<void> {
    await vscode.commands.executeCommand('git.refresh');
  }
}
