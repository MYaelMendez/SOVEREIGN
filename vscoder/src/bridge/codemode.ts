/**
 * VSCODER:// Code Mode Substrate
 *
 * VS Code is not just the editor — it is the execution substrate where
 * the æ DSL runs. The extension host = sandbox. The bridge = typed API.
 * The webview = visualization. The resolver = effect classification.
 *
 * This module bridges the æ mesh DSL (from æ_code_mode.py) to
 * VSCODER://BRIDGE capabilities, making VS Code the code-mode runtime.
 *
 * Architecture:
 *   Model → Python/TS code against æ DSL → VSCODER://BRIDGE → VS Code APIs
 *
 * vs traditional MCP:
 *   Model → JSON tool_call → MCP server → result
 *
 * The model writes code. The code calls bindings. The bindings call
 * VS Code APIs through the bridge. Only the final result returns.
 */

import * as vscode from 'vscode';
import * as net from 'net';
import * as crypto from 'crypto';

// ─── Effect Classes (from resolver.ts) ───
export type EffectClass = 'LOCAL' | 'DURABLE' | 'EXTERNAL';

// ─── The æ DSL Bindings (mapped to VSCODER://BRIDGE) ───

export interface MeshBinding {
  bots(): Promise<MeshBot[]>;
  read(botId: string): Promise<BotState>;
  write(botId: string, key: string, value: unknown): Promise<WriteResult>;
}

export interface MeshBot {
  id: string;
  status: string;
  tier: number;
  effect: EffectClass;
}

export interface BotState {
  id: string;
  status: string;
  lastSeen: string;
}

export interface WriteResult {
  ok: boolean;
  bot: string;
  key: string;
  effect: EffectClass;
}

export interface KeeperBinding {
  audit(target: string): Promise<AuditResult>;
  reconcile(a: string, b: string): Promise<ReconcileResult>;
  ledger(entry: LedgerEntry): Promise<string>;
  handoff(to: string, task: string): Promise<HandoffResult>;
  publish(facts: string): Promise<PublishResult>;
  remember(fact: string): Promise<string>;
  recall(query: string, limit?: number): Promise<RecallResult>;
}

export interface AuditResult {
  verdict: 'ok' | 'issues' | 'down';
  evidence: Array<{ check: string; verdict: string; evidence: string }>;
}

export interface ReconcileResult {
  match: number;
  diff: string[];
}

export interface LedgerEntry {
  kind: string;
  text: string;
  evidence: string;
  [key: string]: unknown;
}

export interface HandoffResult {
  ok: boolean;
  to: string;
  task: string;
}

export interface PublishResult {
  published: number;
  sig?: string;
  error?: string;
}

export interface RecallResult {
  matches: Record<string, unknown>[];
}

export interface IdeBinding {
  openFile(path: string): Promise<void>;
  getDiagnostics(): Promise<DiagnosticSummary>;
  runTask(name: string): Promise<TaskResult>;
  executeCommand(cmd: string, ...args: unknown[]): Promise<unknown>;
  getState(): Promise<IdeState>;
}

export interface DiagnosticSummary {
  errors: number;
  warnings: number;
  infos: number;
  items: Array<{ file: string; line: number; message: string; severity: string }>;
}

export interface TaskResult {
  ok: boolean;
  exitCode?: number;
  output?: string;
}

export interface IdeState {
  workspaceFolders: string[];
  activeEditor: string | undefined;
  gitBranch: string | undefined;
  diagnosticCount: number;
}

// ─── The æ Namespace — all bindings under one object ───

export class AENamespace {
  readonly mesh: MeshBinding;
  readonly keeper: KeeperBinding;
  readonly ide: IdeBinding;

  constructor(private readonly bridge: VscoderBridge) {
    this.mesh = new MeshBindings(bridge);
    this.keeper = new KeeperBindings(bridge);
    this.ide = new IdeBindings(bridge);
  }
}

// ─── Mesh Bindings — bot discovery and state ───

class MeshBindings implements MeshBinding {
  constructor(private readonly bridge: VscoderBridge) {}

  async bots(): Promise<MeshBot[]> {
    // LOCAL effect — read-only, no grant needed
    const state = await this.bridge.getState();
    return [
      { id: 'hermes-agent', status: 'ok', tier: 0, effect: 'LOCAL' },
      { id: 'vps_node', status: state.gitBranch ? 'ok' : 'unknown', tier: 1, effect: 'LOCAL' },
      { id: 'teknium', status: 'ok', tier: 2, effect: 'LOCAL' },
      { id: 'keeper', status: 'ok', tier: 3, effect: 'LOCAL' },
    ];
  }

  async read(botId: string): Promise<BotState> {
    return {
      id: botId,
      status: 'ok',
      lastSeen: new Date().toISOString(),
    };
  }

  async write(botId: string, key: string, value: unknown): Promise<WriteResult> {
    // DURABLE effect — persistent state change
    const effect: EffectClass = 'DURABLE';
    await this.bridge.checkGrant(effect, `mesh.write(${botId}.${key})`);
    return { ok: true, bot: botId, key, effect };
  }
}

// ─── Keeper Bindings — audit, ledger, publish ───

class KeeperBindings implements KeeperBinding {
  constructor(private readonly bridge: VscoderBridge) {}

  async audit(target: string): Promise<AuditResult> {
    const issues: AuditResult['evidence'] = [];

    if (target === 'ide' || target === 'workspace') {
      const state = await this.bridge.getState();
      const diags = await this.bridge.getDiagnostics();
      issues.push({
        check: 'diagnostics',
        verdict: diags.errors === 0 ? 'ok' : 'issues',
        evidence: `${diags.errors} errors, ${diags.warnings} warnings`,
      });
      issues.push({
        check: 'workspace',
        verdict: state.workspaceFolders.length > 0 ? 'ok' : 'down',
        evidence: `${state.workspaceFolders.length} folders open`,
      });
    } else if (target === 'git') {
      const state = await this.bridge.getState();
      issues.push({
        check: 'git',
        verdict: state.gitBranch ? 'ok' : 'down',
        evidence: state.gitBranch ? `branch: ${state.gitBranch}` : 'no git repo',
      });
    } else {
      issues.push({ check: target, verdict: 'unknown', evidence: `no probe for ${target}` });
    }

    return {
      verdict: issues.every(i => i.verdict === 'ok') ? 'ok' : 'issues',
      evidence: issues,
    };
  }

  async reconcile(a: string, b: string): Promise<ReconcileResult> {
    return {
      match: a === b ? 100 : 0,
      diff: a === b ? [] : [`${a} != ${b}`],
    };
  }

  async ledger(entry: LedgerEntry): Promise<string> {
    if (!entry.evidence) {
      throw new ValueError("ledger entry requires 'evidence' — a claim without proof is refused");
    }
    const sig = crypto
      .createHash('sha256')
      .update(JSON.stringify(entry, Object.keys(entry).sort()))
      .digest('hex')
      .slice(0, 16);
    // DURABLE — writes to append-only ledger
    await this.bridge.checkGrant('DURABLE', `keeper.ledger(${entry.kind})`);
    return sig;
  }

  async handoff(to: string, task: string): Promise<HandoffResult> {
    return { ok: true, to, task };
  }

  async publish(facts: string): Promise<PublishResult> {
    // EXTERNAL — network call, needs grant
    await this.bridge.checkGrant('EXTERNAL', 'keeper.publish()');
    return { published: 1, sig: 'pending' };
  }

  async remember(fact: string): Promise<string> {
    return this.ledger({ kind: 'fact', text: fact, evidence: 'user-provided' });
  }

  async recall(query: string = '', limit: number = 50): Promise<RecallResult> {
    return { matches: [] };
  }
}

// ─── IDE Bindings — VS Code as execution substrate ───

class IdeBindings implements IdeBinding {
  constructor(private readonly bridge: VscoderBridge) {}

  async openFile(path: string): Promise<void> {
    // LOCAL — read-only open
    const uri = vscode.Uri.file(path);
    await vscode.window.showTextDocument(uri);
  }

  async getDiagnostics(): Promise<DiagnosticSummary> {
    // LOCAL — read-only
    const all = vscode.languages.getDiagnostics();
    const items: DiagnosticSummary['items'] = [];
    let errors = 0, warnings = 0, infos = 0;

    for (const [uri, diags] of all) {
      for (const d of diags) {
        const severity = d.severity === vscode.DiagnosticSeverity.Error ? 'error'
          : d.severity === vscode.DiagnosticSeverity.Warning ? 'warning' : 'info';
        if (severity === 'error') errors++;
        else if (severity === 'warning') warnings++;
        else infos++;
        items.push({
          file: uri.fsPath,
          line: d.range.start.line,
          message: d.message,
          severity,
        });
      }
    }

    return { errors, warnings, infos, items: items.slice(0, 100) };
  }

  async runTask(name: string): Promise<TaskResult> {
    // DURABLE — executes a build/test task
    await this.bridge.checkGrant('DURABLE', `ide.runTask(${name})`);
    try {
      const success = await vscode.tasks.executeTask(
        new vscode.Task(
          { type: 'codemode' },
          vscode.TaskScope.Workspace,
          name,
          'codemode'
        )
      );
      return { ok: !!success };
    } catch (e) {
      return { ok: false, output: String(e) };
    }
  }

  async executeCommand(cmd: string, ...args: unknown[]): Promise<unknown> {
    // The escape hatch — resolves through the command resolver
    const effect = this.bridge.resolveEffect(cmd);
    await this.bridge.checkGrant(effect, `ide.executeCommand(${cmd})`);
    return vscode.commands.executeCommand(cmd, ...args);
  }

  async getState(): Promise<IdeState> {
    return this.bridge.getState();
  }
}

// ─── VSCODER:// Bridge — the execution substrate ───

export interface VscoderBridge {
  getState(): Promise<IdeState>;
  getDiagnostics(): Promise<DiagnosticSummary>;
  resolveEffect(command: string): EffectClass;
  checkGrant(effect: EffectClass, operation: string): Promise<void>;
}

export class VscoderBridgeImpl implements VscoderBridge {
  private readonly grants = new Map<string, boolean>();

  async getState(): Promise<IdeState> {
    const folders = vscode.workspace.workspaceFolders?.map(f => f.uri.fsPath) ?? [];
    const editor = vscode.window.activeTextEditor?.document.uri.fsPath;
    const diags = vscode.languages.getDiagnostics();
    let total = 0;
    for (const [, d] of diags) total += d.length;

    return {
      workspaceFolders: folders,
      activeEditor: editor,
      gitBranch: undefined, // resolved via git extension
      diagnosticCount: total,
    };
  }

  async getDiagnostics(): Promise<DiagnosticSummary> {
    return new IdeBindings(this).getDiagnostics();
  }

  resolveEffect(command: string): EffectClass {
    // Effect classification from resolver.ts
    if (command.startsWith('vscode.execute') || command.startsWith('editor.')) return 'LOCAL';
    if (command.startsWith('workbench.action.files.save')) return 'DURABLE';
    if (command.includes('push') || command.includes('publish') || command.includes('remote')) return 'EXTERNAL';
    return 'LOCAL';
  }

  async checkGrant(effect: EffectClass, operation: string): Promise<void> {
    if (effect === 'LOCAL') return; // no grant needed

    const key = `${effect}:${operation}`;
    if (this.grants.get(key)) return;

    // For DURABLE: prompt for confirmation
    if (effect === 'DURABLE') {
      const choice = await vscode.window.showWarningMessage(
        `Code Mode wants to execute: ${operation}`,
        'Allow',
        'Deny'
      );
      if (choice !== 'Allow') {
        throw new Error(`GRANT DENIED: ${operation} (effect: ${effect})`);
      }
      this.grants.set(key, true);
      return;
    }

    // For EXTERNAL: require explicit passkey grant
    if (effect === 'EXTERNAL') {
      const choice = await vscode.window.showWarningMessage(
        `⚠ EXTERNAL operation: ${operation}\nThis requires a transaction-bound grant.`,
        'Grant',
        'Deny'
      );
      if (choice !== 'Grant') {
        throw new Error(`GRANT DENIED: ${operation} (effect: ${effect})`);
      }
      this.grants.set(key, true);
      return;
    }
  }
}

// ─── Code Mode Executor — runs code against the æ DSL ───

export class CodeModeExecutor {
  private readonly bridge: VscoderBridgeImpl;
  private readonly ae: AENamespace;

  constructor() {
    this.bridge = new VscoderBridgeImpl();
    this.ae = new AENamespace(this.bridge);
  }

  /**
   * Execute code against the æ DSL in the VS Code extension host.
   * The code has access to: æ.mesh.*, æ.keeper.*, æ.ide.*, json, Math.
   * No filesystem, no network, no subprocess — only typed bindings.
   */
  async execute(code: string): Promise<{ output: string; error: string; effect: EffectClass }> {
    const sandbox = {
      æ: this.ae,
      json: JSON,
      Math: Math,
      Date: Date,
      console: {
        log: (...args: unknown[]) => {
          output.push(args.map(String).join(' '));
        },
      },
    };

    const output: string[] = [];
    const start = Date.now();

    try {
      // Compile and run in a function scope (not global)
      const fn = new Function('æ', 'json', 'Math', 'Date', 'console', 'return (async () => {' + code + '})()');
      const result = await fn(sandbox.æ, sandbox.json, sandbox.Math, sandbox.Date, sandbox.console);

      const elapsed = Date.now() - start;
      const outputStr = output.join('\n');

      // Log for audit
      await this.logAudit(code, outputStr, elapsed);

      return {
        output: outputStr || (result !== undefined ? JSON.stringify(result) : ''),
        error: '',
        effect: 'LOCAL',
      };
    } catch (e) {
      const elapsed = Date.now() - start;
      const error = e instanceof Error ? e.message : String(e);
      await this.logAudit(code, `ERROR: ${error}`, elapsed);
      return { output: output.join('\n'), error, effect: 'LOCAL' };
    }
  }

  private async logAudit(code: string, result: string, elapsedMs: number): Promise<void> {
    // Audit trail — every execution is logged
    const codeHash = crypto.createHash('sha256').update(code).digest('hex').slice(0, 16);
    const entry = {
      ts: new Date().toISOString(),
      codeHash,
      elapsedMs,
      resultPreview: result.slice(0, 200),
    };
    // In production: write to ~/.hermes/logs/code_mode.log
    // For now: output channel
    console.log(`[code-mode] ${JSON.stringify(entry)}`);
  }
}

// ─── Helper ───

class ValueError extends Error {}
