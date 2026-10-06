import * as vscode from 'vscode';

// ── Types ──────────────────────────────────────────────────────────────────

export interface GitStatusInfo {
  branch: string;
  changes: number;
  commitTemplate: string;
  rootUri: string | undefined;
}

export interface GitRepositoryInfo {
  rootUri: string | undefined;
  branch: string;
  changes: number;
  commitTemplate: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

interface GitAPI {
  repositories: GitRepository[];
}

interface GitRepository {
  rootUri: vscode.Uri;
  state: {
    HEAD: { name: string } | undefined;
    workingTreeChanges: { uri: vscode.Uri }[];
    indexChanges: { uri: vscode.Uri }[];
    mergeChanges: { uri: vscode.Uri }[];
  };
  inputBox: { value: string };
  commitTemplate?: string;
}

function getGitAPI(): GitAPI | undefined {
  const gitExtension = vscode.extensions.getExtension('vscode.git');
  if (!gitExtension) return undefined;
  const exports = gitExtension.exports as { getAPI(version: number): GitAPI };
  return exports.getAPI(1);
}

// ── Git Operations ──────────────────────────────────────────────────────────

/**
 * Get git status information.
 * Executes `git.status` and returns structured data from the SCM API.
 */
export async function status(): Promise<GitStatusInfo> {
  await vscode.commands.executeCommand('git.status');
  const api = getGitAPI();
  const repo = api?.repositories[0];
  return {
    branch: repo?.state.HEAD?.name ?? 'unknown',
    changes: (repo?.state.workingTreeChanges.length ?? 0)
      + (repo?.state.indexChanges.length ?? 0)
      + (repo?.state.mergeChanges.length ?? 0),
    commitTemplate: repo?.commitTemplate ?? '',
    rootUri: repo?.rootUri.fsPath,
  };
}

/**
 * Show git diff.
 * Executes `git.diff` to open the diff view.
 */
export async function diff(): Promise<void> {
  await vscode.commands.executeCommand('git.diff');
}

/**
 * Show/create branches.
 * Executes `git.branch` to open the branch quick pick.
 */
export async function branch(): Promise<void> {
  await vscode.commands.executeCommand('git.branch');
}

/**
 * Commit changes.
 * Optionally sets the commit message, then executes `git.commit`.
 */
export async function commit(message?: string): Promise<void> {
  const api = getGitAPI();
  if (message && api?.repositories[0]) {
    api.repositories[0].inputBox.value = message;
  }
  await vscode.commands.executeCommand('git.commit');
}

/**
 * Push to remote.
 * Executes `git.push`.
 */
export async function push(): Promise<void> {
  await vscode.commands.executeCommand('git.push');
}

// ── Utility Functions ───────────────────────────────────────────────────────

/** Check if git is available in the current workspace. */
export function isGitAvailable(): boolean {
  const api = getGitAPI();
  return api !== undefined && api.repositories.length > 0;
}

/** Get the repository root path. */
export function getRepositoryRoot(): string | undefined {
  return getGitAPI()?.repositories[0]?.rootUri.fsPath;
}

/** Get the number of pending changes. */
export function getChangeCount(): number {
  const repo = getGitAPI()?.repositories[0];
  if (!repo) return 0;
  return repo.state.workingTreeChanges.length
    + repo.state.indexChanges.length
    + repo.state.mergeChanges.length;
}

/** Get the commit template. */
export function getCommitTemplate(): string {
  return getGitAPI()?.repositories[0]?.commitTemplate ?? '';
}

/** Set the commit message in the input box. */
export function setCommitMessage(message: string): void {
  const repo = getGitAPI()?.repositories[0];
  if (repo) {
    repo.inputBox.value = message;
  }
}

/** Get the current commit message from the input box. */
export function getCommitMessage(): string {
  return getGitAPI()?.repositories[0]?.inputBox.value ?? '';
}

/** Get comprehensive repository info. */
export function getRepositoryInfo(): GitRepositoryInfo {
  const repo = getGitAPI()?.repositories[0];
  return {
    rootUri: repo?.rootUri.fsPath,
    branch: repo?.state.HEAD?.name ?? 'unknown',
    changes: repo
      ? repo.state.workingTreeChanges.length
        + repo.state.indexChanges.length
        + repo.state.mergeChanges.length
      : 0,
    commitTemplate: repo?.commitTemplate ?? '',
  };
}