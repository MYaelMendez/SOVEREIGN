/**
 * VSCODER://BRIDGE — Build/Test/Debug/Task Controller
 * Unified interface to VS Code's task, test, and debug APIs.
 */

import * as vscode from 'vscode';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface TaskInfo {
  name: string;
  source: string;
  definition: string;
  isBackground: boolean;
  group: string;
}

export interface DebugSessionInfo {
  isActive: boolean;
  sessionId?: string;
  sessionType?: string;
  sessionName?: string;
  breakpoints: number;
}

export class TaskController {
  async getTasks(): Promise<TaskInfo[]> {
    const tasks = await vscode.tasks.fetchTasks();
    return tasks.map(t => ({
      name: t.name,
      source: t.source,
      definition: (t.definition as any)?.type || '',
      isBackground: t.isBackground,
      group: (t.group as any)?.id || '',
    }));
  }

  async runTask(taskName: string): Promise<vscode.TaskExecution> {
    const tasks = await vscode.tasks.fetchTasks();
    const task = tasks.find(t => t.name === taskName);
    if (!task) {
      throw new Error(`Task "${taskName}" not found`);
    }
    return vscode.tasks.executeTask(task);
  }

  async runBuildTask(): Promise<vscode.TaskExecution> {
    const tasks = await vscode.tasks.fetchTasks();
    const buildTasks = tasks.filter(t => (t.group as any)?.id === vscode.TaskGroup.Build.id);
    if (buildTasks.length === 0) {
      throw new Error('No build task found');
    }
    return vscode.tasks.executeTask(buildTasks[0]);
  }

  async runTestTask(): Promise<vscode.TaskExecution> {
    const tasks = await vscode.tasks.fetchTasks();
    const testTasks = tasks.filter(t => (t.group as any)?.id === vscode.TaskGroup.Test.id);
    if (testTasks.length === 0) {
      throw new Error('No test task found');
    }
    return vscode.tasks.executeTask(testTasks[0]);
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

  async runTests(testPattern?: string): Promise<{ passed: number; failed: number; skipped: number; output: string }> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    const cmd = testPattern
      ? `python -m pytest ${testPattern} --tb=short -q`
      : 'python -m pytest --tb=short -q';
    const result = await this.executeCommand(cmd, workspaceRoot);
    const output = result.stdout + result.stderr;
    const passed = (output.match(/(\d+) passed/g) || []).reduce((sum, m) => sum + parseInt(m), 0);
    const failed = (output.match(/(\d+) failed/g) || []).reduce((sum, m) => sum + parseInt(m), 0);
    const skipped = (output.match(/(\d+) skipped/g) || []).reduce((sum, m) => sum + parseInt(m), 0);
    return { passed, failed, skipped, output };
  }

  async runBuild(command?: string): Promise<{ success: boolean; output: string }> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    const cmd = command || 'python -m py_compile';
    const result = await this.executeCommand(cmd, workspaceRoot);
    return {
      success: result.exitCode === 0,
      output: result.stdout + result.stderr,
    };
  }
}

export class DebugController {
  async startDebugging(config?: vscode.DebugConfiguration): Promise<boolean> {
    const debugConfig: vscode.DebugConfiguration = config || {
      type: 'python',
      name: 'VSCODER Debug',
      request: 'launch',
      program: '${file}',
      console: 'integratedTerminal',
    };
    return vscode.debug.startDebugging(
      vscode.workspace.workspaceFolders?.[0],
      debugConfig
    );
  }

  async stopDebugging(): Promise<void> {
    await vscode.debug.stopDebugging(vscode.debug.activeDebugSession);
  }

  getSessionInfo(): DebugSessionInfo {
    const session = vscode.debug.activeDebugSession;
    return {
      isActive: session !== undefined,
      sessionId: session?.id,
      sessionType: session?.type,
      sessionName: session?.name,
      breakpoints: vscode.debug.breakpoints.length,
    };
  }

  async addBreakpoint(filePath: string, line: number, condition?: string): Promise<void> {
    const location = new vscode.Location(
      vscode.Uri.file(filePath),
      new vscode.Position(line, 0)
    );
    const bp = new vscode.SourceBreakpoint(location, true, condition);
    vscode.debug.addBreakpoints([bp]);
  }

  async removeBreakpoint(filePath: string, line: number): Promise<void> {
    const bps = vscode.debug.breakpoints.filter(
      b => (b as any)?.location?.uri?.fsPath === filePath &&
           (b as any)?.location?.range?.start?.line === line
    );
    vscode.debug.removeBreakpoints(bps);
  }

  async getBreakpoints(): Promise<Array<{ file: string; line: number; enabled: boolean; condition?: string }>> {
    return vscode.debug.breakpoints.map(b => ({
      file: (b as any)?.location?.uri?.fsPath || '',
      line: (b as any)?.location?.range?.start?.line || 0,
      enabled: b.enabled,
      condition: (b as any)?.condition,
    }));
  }

  async continueDebugging(): Promise<void> {
    await vscode.commands.executeCommand('workbench.action.debug.continue');
  }

  async stepOver(): Promise<void> {
    await vscode.commands.executeCommand('workbench.action.debug.stepOver');
  }

  async stepInto(): Promise<void> {
    await vscode.commands.executeCommand('workbench.action.debug.stepInto');
  }

  async stepOut(): Promise<void> {
    await vscode.commands.executeCommand('workbench.action.debug.stepOut');
  }
}
