/**
 * VSCODER://BRIDGE — Terminal Controller
 * Full terminal control: create, send, read, dispose.
 */

import * as vscode from 'vscode';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface TerminalInfo {
  name: string;
  isBusy: boolean;
}

export class TerminalController {
  getTerminals(): TerminalInfo[] {
    return vscode.window.terminals.map(t => ({
      name: t.name,
      isBusy: false,
    }));
  }

  async createTerminal(name: string, cwd?: string): Promise<vscode.Terminal> {
    const terminal = vscode.window.createTerminal({ name, cwd });
    terminal.show();
    return terminal;
  }

  async sendCommand(terminalName: string, command: string): Promise<void> {
    const terminal = vscode.window.terminals.find(t => t.name === terminalName);
    if (!terminal) {
      throw new Error(`Terminal "${terminalName}" not found`);
    }
    terminal.sendText(command, true);
  }

  async executeCommand(command: string, cwd?: string): Promise<{ stdout: string; stderr: string; exitCode: number }> {
    try {
      const { stdout, stderr } = await execAsync(command, {
        cwd: cwd || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
        timeout: 120000,
        maxBuffer: 10 * 1024 * 1024,
      });
      return { stdout, stderr, exitCode: 0 };
    } catch (e: unknown) {
      return {
        stdout: (e as Error & { stdout?: string }).stdout || '',
        stderr: (e as Error & { stderr?: string }).stderr || (e instanceof Error ? e.message : String(e)),
        exitCode: (e as { code?: number }).code ?? 1,
      };
    }
  }

  async disposeTerminal(terminalName: string): Promise<void> {
    const terminal = vscode.window.terminals.find(t => t.name === terminalName);
    if (terminal) {
      terminal.dispose();
    }
  }

  async runInNewTerminal(name: string, command: string, cwd?: string): Promise<vscode.Terminal> {
    const terminal = await this.createTerminal(name, cwd);
    await this.sendCommand(name, command);
    return terminal;
  }
}
