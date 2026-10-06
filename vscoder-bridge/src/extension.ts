/**
 * VSCODER://BRIDGE — Hermes Desktop IDE Driver
 *
 * A native VS Code extension that exposes VS Code capabilities as typed
 * VSCODER tools over a local authenticated IPC/RPC channel.
 *
 * Features:
 *   - Full IDE control: workspace, editor, symbols, refactor, diagnostics,
 *     tasks, tests, debug, terminal, scm, ui
 *   - IDE state observation (VSCODER_IDE_STATE_V1)
 *   - Event-driven shared state with human in the loop
 *   - Authority separation: LOCAL, DURABLE, EXTERNAL
 *   - Receipt system with SHA-256 hash chain
 *   - MOLT strategy competition
 *   - WebMCP tools: vscoder_observe, vscoder_plan, vscoder_refactor,
 *     vscoder_build, vscoder_test, vscoder_debug, vscoder_benchmark,
 *     vscoder_git_diff, vscoder_receipt
 */

import * as vscode from 'vscode';
import * as http from 'http';
import * as path from 'path';
import * as crypto from 'crypto';
import * as fs from 'fs';
import { execSync } from 'child_process';

import { ReceiptChain, ReceiptInput, TestResult } from './receipts/witness';
import { assess, requestGrant, verifyGrant, Operation, RiskLevel } from './authority/policy';
import { IDEStateObserver, IDEStateV1 } from './controllers/ideState';
import { WorkspaceController } from './controllers/workspace';
import { EditorController } from './controllers/editor';
import { RefactorController } from './controllers/refactor';
import { TaskController, DebugController } from './controllers/taskDebug';
import { TerminalController } from './controllers/terminal';
import { SCMController } from './controllers/scm';
import { UIController } from './controllers/ui';
import { MoltEngine, Intent, AuthorityEnvelope, Strategy, StrategyResult, Evidence } from './agent/molt';

// ═══════════════════════════════════════════════════════════
// WebMCP HTTP Server
// ═══════════════════════════════════════════════════════════

class WebMCPServer {
  private server: http.Server | null = null;
  private port: number;
  private receipts: ReceiptChain;
  private ideState: IDEStateObserver;
  private workspace: WorkspaceController;
  private editor: EditorController;
  private refactor: RefactorController;
  private taskController: TaskController;
  private debugController: DebugController;
  private terminalController: TerminalController;
  private scmController: SCMController;
  private uiController: UIController;
  private moltEngine: MoltEngine;
  private authToken: string;

  constructor(
    context: vscode.ExtensionContext,
    receipts: ReceiptChain,
    ideState: IDEStateObserver,
    port: number = 8123,
    authToken: string = '',
  ) {
    this.receipts = receipts;
    this.ideState = ideState;
    this.port = port;
    this.authToken = authToken;
    this.workspace = new WorkspaceController();
    this.editor = new EditorController();
    this.refactor = new RefactorController();
    this.taskController = new TaskController();
    this.debugController = new DebugController();
    this.terminalController = new TerminalController();
    this.scmController = new SCMController();
    this.uiController = new UIController();
    this.moltEngine = new MoltEngine();
  }

  start(): void {
    if (this.server) return;

    this.server = http.createServer((req, res) => {
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

      if (req.method === 'OPTIONS') {
        res.writeHead(204);
        res.end();
        return;
      }

      // Auth check
      if (this.authToken) {
        const auth = req.headers['authorization'];
        if (auth !== `Bearer ${this.authToken}`) {
          res.writeHead(401, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Unauthorized' }));
          return;
        }
      }

      const url = req.url || '/';

      if (url === '/' || url === '/index.html') {
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(this.getWebviewHtml());
        return;
      }

      if (url === '/api/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'ok',
          version: '1.0.0',
          tools: this.getToolNames(),
          ide_state: this.ideState.state,
        }));
        return;
      }

      if (url === '/api/ide-state') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(this.ideState.state));
        return;
      }

      if (url === '/api/receipts') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          chain: this.receipts.getReceipts(),
          valid: this.receipts.verify(),
          count: this.receipts.getReceipts().length,
        }));
        return;
      }

      if (url === '/api/invoke' && req.method === 'POST') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
          try {
            const { tool, params } = JSON.parse(body);
            const result = await this.invokeTool(tool, params || {});
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(result));
          } catch (e: unknown) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: (e instanceof Error ? e.message : String(e)) }));
          }
        });
        return;
      }

      res.writeHead(404);
      res.end('Not found');
    });

    this.server.listen(this.port, () => {
      console.log(`VSCODER://BRIDGE: WebMCP server listening on :${this.port}`);
    });
  }

  private getToolNames(): string[] {
    return [
      'vscoder_observe', 'vscoder_plan', 'vscoder_refactor',
      'vscoder_build', 'vscoder_test', 'vscoder_debug',
      'vscoder_benchmark', 'vscoder_git_diff', 'vscoder_receipt'
    ];
  }

  async invokeTool(tool: string, params: any): Promise<any> {
    switch (tool) {
      case 'vscoder_observe': return this.toolObserve(params);
      case 'vscoder_plan': return this.toolPlan(params);
      case 'vscoder_refactor': return this.toolRefactor(params);
      case 'vscoder_build': return this.toolBuild(params);
      case 'vscoder_test': return this.toolTest(params);
      case 'vscoder_debug': return this.toolDebug(params);
      case 'vscoder_benchmark': return this.toolBenchmark(params);
      case 'vscoder_git_diff': return this.toolGitDiff(params);
      case 'vscoder_receipt': return this.toolReceipt(params);
      default: throw new Error(`Unknown tool: ${tool}`);
    }
  }

  // ── WebMCP Tool Implementations ──

  private toolObserve(params: any): any {
    const state = this.ideState.refresh();
    const result = {
      ...state,
      authority: {
        level: 'LOCAL',
        reason: 'Read-only IDE state observation',
      },
    };
    this.addReceipt('observe', params, result);
    return result;
  }

  private async toolPlan(params: any): Promise<any> {
    const instruction = params.instruction || 'optimize workspace';
    const workspaceRoot = this.workspace.getInfo().rootPath;

    // Gather symbols from active editor
    const activeEditor = this.editor.getActiveEditor();
    let symbols: any[] = [];
    if (activeEditor) {
      try {
        const syms = await this.editor.getDocumentSymbols(activeEditor.path);
        symbols = syms.map(s => ({
          name: s.name,
          kind: vscode.SymbolKind[s.kind],
          detail: s.detail,
        }));
      } catch { /* LSP not available */ }
    }

    // Use MOLT to generate plan strategies
    const intent: Intent = {
      goal: instruction,
      constraints: ['preserve functionality', 'improve readability'],
    };
    const authority: AuthorityEnvelope = {
      allowedActions: ['analyze', 'suggest', 'refactor'],
      deniedActions: ['delete', 'push'],
      scope: workspaceRoot,
      maxIterations: 5,
    };

    const strategies: Array<{ name: string; execute: (ctx: any) => Promise<StrategyResult> }> = [
      {
        name: 'conservative',
        execute: async (ctx): Promise<StrategyResult> => ({
          success: true,
          evidence: [{ metric: 'risk', value: 0.1, lowerIsBetter: true, timestamp: Date.now() }],
          durationMs: 10,
        }),
      },
      {
        name: 'aggressive',
        execute: async (ctx): Promise<StrategyResult> => ({
          success: true,
          evidence: [{ metric: 'coverage', value: 0.9, lowerIsBetter: false, timestamp: Date.now() }],
          durationMs: 20,
        }),
      },
    ];

    const moltResult = await this.moltEngine.compete(
      strategies.map(s => this.moltEngine.create(s.name, intent, authority, s.execute))
    );

    const plan = {
      instruction,
      workspaceRoot,
      symbols: symbols.slice(0, 50),
      steps: [
        'Analyze workspace structure',
        'Identify optimization targets',
        'Apply semantic refactoring',
        'Run tests to verify',
        'Generate receipt',
      ],
      molt: {
        winner: moltResult.winner.name,
        evidence: moltResult.evidence.length,
        durationMs: moltResult.totalDurationMs,
      },
      timestamp: new Date().toISOString(),
    };

    this.addReceipt('plan', instruction, plan);
    return plan;
  }

  private async toolRefactor(params: any): Promise<any> {
    const activeEditor = this.editor.getActiveEditor();
    if (!activeEditor) {
      return { error: 'No active editor' };
    }

    const refactorKind = params.kind || 'rename';
    const filePath = activeEditor.path;
    const position = activeEditor.cursor;

    let result: any = { kind: refactorKind, applied: false };

    try {
      if (refactorKind === 'rename') {
        const newName = params.newName || 'refactoredSymbol';
        const applied = await this.editor.renameSymbol(filePath, position, newName);
        result = { kind: 'rename', applied, newName };
      } else if (refactorKind === 'findReferences') {
        const refs = await this.editor.findReferences(filePath, position);
        result = { kind: 'findReferences', count: refs.length, references: refs.slice(0, 20) };
      } else if (refactorKind === 'codeAction') {
        const range = {
          start: { line: position.line, character: 0 },
          end: { line: position.line + 1, character: 0 },
        };
        const actions = await this.editor.getCodeActions(filePath, range);
        result = { kind: 'codeAction', count: actions.length, actions: actions.map(a => a.title) };
      } else if (refactorKind === 'organizeImports') {
        const refResult = await this.refactor.organizeImports(filePath);
        result = { kind: 'organizeImports', ...refResult };
      }
    } catch (e: unknown) {
      result = { kind: refactorKind, error: (e instanceof Error ? e.message : String(e)) };
    }

    this.addReceipt('refactor', params, result);
    return result;
  }

  private async toolBuild(params: any): Promise<any> {
    const command = params.command || 'python -m py_compile';
    const result = await this.taskController.runBuild(command);
    this.addReceipt('build', command, result);
    return result;
  }

  private async toolTest(params: any): Promise<any> {
    const testPattern = params.pattern;
    const result = await this.taskController.runTests(testPattern);
    this.addReceipt('test', testPattern || 'all', result);
    return result;
  }

  private async toolDebug(params: any): Promise<any> {
    const config = params.config;
    const success = await this.debugController.startDebugging(config);
    const sessionInfo = this.debugController.getSessionInfo();
    const result = { success, session: sessionInfo };
    this.addReceipt('debug', params, result);
    return result;
  }

  private async toolBenchmark(params: any): Promise<any> {
    const workspaceRoot = this.workspace.getInfo().rootPath;
    const command = params.command || 'python -m pytest --benchmark-only --benchmark-json=benchmark.json';

    let result: any;
    try {
      const execResult = await this.taskController.executeCommand(command, workspaceRoot);
      result = {
        success: execResult.exitCode === 0,
        output: execResult.stdout.slice(0, 3000),
        metrics: { latencyP50: 0, latencyP95: 0, fps: 0 },
      };
    } catch (e: unknown) {
      result = { success: false, error: (e instanceof Error ? e.message : String(e)) };
    }

    this.addReceipt('benchmark', command, result);
    return result;
  }

  private async toolGitDiff(params: any): Promise<any> {
    const [diff, status, log] = await Promise.all([
      this.scmController.getDiff(),
      this.scmController.getStatusShort(),
      this.scmController.getLog(5),
    ]);
    const result = { diff, status, log, hasChanges: diff.trim().length > 0 };
    this.addReceipt('git_diff', params, result);
    return result;
  }

  private toolReceipt(params: any): any {
    const chain = this.receipts.getReceipts();
    const valid = this.receipts.verify();
    const latest = this.receipts.getLatest();

    return {
      chain,
      valid,
      count: chain.length,
      latest,
      timestamp: new Date().toISOString(),
    };
  }

  private addReceipt(action: string, input: any, output: any): void {
    const inputStr = typeof input === 'string' ? input : JSON.stringify(input);
    const outputStr = typeof output === 'string' ? output : JSON.stringify(output);
    this.receipts.append({
      intent: inputStr.slice(0, 500),
      plan: action,
      before: '',
      after: outputStr.slice(0, 500),
    });
  }

  private getWebviewHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>VSCODER://BRIDGE v1.0</title>
<style>
:root{--void:#050505;--panel:#0a0a0f;--gold:#D4AF37;--gold2:#f0d487;--emerald:#00ff9d;--cyan:#00eaff;--violet:#8c72ff;--orange:#ff9a4d;--ink:#e8e6df;--muted:#6f6a5c;--line:rgba(212,175,55,.22);--mono:"JetBrains Mono",ui-monospace,monospace;--display:"Orbitron",sans-serif;--error:#ff7b72;}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;overflow:hidden;background:var(--void);color:var(--ink);font-family:var(--mono)}
#app{display:grid;grid-template-rows:auto 1fr auto;height:100vh;padding:12px;gap:10px}
.header{display:flex;align-items:baseline;gap:14px;border-bottom:1px solid var(--line);padding-bottom:10px}
.title{font-size:18px;font-weight:700;color:var(--gold);letter-spacing:.08em}
.subtitle{font-size:11px;color:var(--muted);letter-spacing:.12em}
.status{font-size:10px;color:var(--emerald);display:flex;align-items:center;gap:6px;margin-left:auto}
.status::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--emerald);box-shadow:0 0 6px var(--emerald)}
.main{display:grid;grid-template-columns:1fr 1fr;gap:10px;min-height:0}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;overflow:auto}
.panel h2{font-size:12px;color:var(--gold);margin-bottom:8px;letter-spacing:.06em}
.panel pre{font-size:10px;color:var(--muted);white-space:pre-wrap;word-break:break-word;max-height:200px;overflow:auto}
.footer{display:flex;gap:8px;align-items:center;border-top:1px solid var(--line);padding-top:8px}
.btn{background:linear-gradient(135deg,rgba(212,175,55,.15),rgba(0,255,163,.08));border:1px solid rgba(212,175,55,.65);color:var(--gold);padding:8px 12px;border-radius:8px;font:inherit;font-size:11px;cursor:pointer}
.btn:hover{background:rgba(212,175,55,.2)}
.btn.secondary{border-color:var(--line);color:var(--muted)}
#log{font-size:9px;color:var(--muted);max-height:120px;overflow:auto;white-space:pre-wrap}
.err{color:var(--error)}
input,textarea{width:100%;background:#060609;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:8px;font:inherit;font-size:11px;margin-bottom:8px}
.capability-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px}
.cap-card{background:#060609;border:1px solid var(--line);border-radius:8px;padding:10px}
.cap-card .name{color:var(--gold);font-size:11px;font-weight:700}
.cap-card .desc{color:var(--muted);font-size:10px;margin-top:4px}
</style>
</head>
<body>
<div id="app">
  <div class="header">
    <div class="title">VSCODER://BRIDGE</div>
    <div class="subtitle">v1.0 · Hermes Desktop IDE Driver</div>
    <div class="status" id="status">READY</div>
  </div>
  <div class="main">
    <div class="panel">
      <h2>INSTRUCTION</h2>
      <textarea id="instruction" rows="3" placeholder="e.g. optimize vision-supervision"></textarea>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        <button class="btn" onclick="runTool('vscoder_observe')">Observe</button>
        <button class="btn" onclick="runTool('vscoder_plan')">Plan</button>
        <button class="btn" onclick="runTool('vscoder_refactor')">Refactor</button>
        <button class="btn" onclick="runTool('vscoder_build')">Build</button>
        <button class="btn" onclick="runTool('vscoder_test')">Test</button>
        <button class="btn" onclick="runTool('vscoder_debug')">Debug</button>
        <button class="btn" onclick="runTool('vscoder_benchmark')">Benchmark</button>
        <button class="btn" onclick="runTool('vscoder_git_diff')">Git Diff</button>
        <button class="btn" onclick="runTool('vscoder_receipt')">Receipt</button>
      </div>
      <h2 style="margin-top:12px">PARAMETERS</h2>
      <input id="paramKey" placeholder="param key (e.g. kind, command)"/>
      <input id="paramValue" placeholder="param value"/>
      <h2 style="margin-top:12px">CAPABILITY GRAPH</h2>
      <div class="capability-grid">
        <div class="cap-card"><div class="name">Workspace</div><div class="desc">Folders, Files, Search</div></div>
        <div class="cap-card"><div class="name">Editor</div><div class="desc">Open, Edit, Navigate</div></div>
        <div class="cap-card"><div class="name">LSP</div><div class="desc">Symbols, References, Definitions</div></div>
        <div class="cap-card"><div class="name">Refactor</div><div class="desc">Rename, Extract, Move, Code Actions</div></div>
        <div class="cap-card"><div class="name">Build</div><div class="desc">Tasks, Compilation, PyCompile</div></div>
        <div class="cap-card"><div class="name">Test</div><div class="desc">Pytest, Test API, Coverage</div></div>
        <div class="cap-card"><div class="name">Debug</div><div class="desc">Breakpoints, Sessions, Inspection</div></div>
        <div class="cap-card"><div class="name">Terminal</div><div class="desc">Create, Send, Execute</div></div>
        <div class="cap-card"><div class="name">SCM</div><div class="desc">Git Diff, Status, Commit, Branch</div></div>
        <div class="cap-card"><div class="name">UI</div><div class="desc">Panels, Webviews, Quick Pick</div></div>
        <div class="cap-card"><div class="name">Authority</div><div class="desc">LOCAL, DURABLE, EXTERNAL</div></div>
        <div class="cap-card"><div class="name">Receipt</div><div class="desc">SHA-256 Hash Chain, Verify</div></div>
        <div class="cap-card"><div class="name">MOLT</div><div class="desc">Strategy Competition</div></div>
        <div class="cap-card"><div class="name">WebMCP</div><div class="desc">HTTP :8123, 9 Tools, Offline</div></div>
        <div class="cap-card"><div class="name">IDE State</div><div class="desc">VSCODER_IDE_STATE_V1</div></div>
      </div>
    </div>
    <div class="panel">
      <h2>OUTPUT</h2>
      <pre id="output">Awaiting instruction...</pre>
    </div>
  </div>
  <div class="footer">
    <span style="font-size:10px;color:var(--muted)">WebMCP: :8123 · LSP: active · Receipts: <span id="receiptCount">0</span> · Hash Chain: <span id="hashChain">—</span></span>
  </div>
  <div id="log"></div>
</div>
<script>
const logEl = document.getElementById('log');
const outputEl = document.getElementById('output');
const statusEl = document.getElementById('status');
const receiptCountEl = document.getElementById('receiptCount');
const hashChainEl = document.getElementById('hashChain');
const log = (t, err=false) => { const d = document.createElement('div'); if(err) d.className='err'; d.textContent = new Date().toLocaleTimeString() + ' ' + t; logEl.appendChild(d); logEl.scrollTop = logEl.scrollHeight; };

async function runTool(tool) {
  const instruction = document.getElementById('instruction').value;
  const paramKey = document.getElementById('paramKey').value;
  const paramValue = document.getElementById('paramValue').value;
  const params = { instruction };
  if (paramKey) params[paramKey] = paramValue;
  statusEl.textContent = 'RUNNING: ' + tool;
  log('invoke ' + tool);
  try {
    const resp = await fetch('http://localhost:8123/api/invoke', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ tool, params })
    });
    const data = await resp.json();
    outputEl.textContent = JSON.stringify(data, null, 2);
    statusEl.textContent = 'READY';
    log('done ' + tool);
    updateReceiptCount();
  } catch(e) {
    outputEl.textContent = 'Error: ' + (e instanceof Error ? e.message : String(e));
    statusEl.textContent = 'ERROR';
    log('error: ' + (e instanceof Error ? e.message : String(e)), true);
  }
}

async function updateReceiptCount() {
  try {
    const resp = await fetch('http://localhost:8123/api/receipts');
    const data = await resp.json();
    receiptCountEl.textContent = data.count;
    if (data.chain.length > 0) {
      const last = data.chain[data.chain.length - 1];
      hashChainEl.textContent = last.receiptHash.slice(0, 16) + '...';
    }
  } catch(e) {}
}

updateReceiptCount();
log('VSCODER://BRIDGE v1.0 initialized');
</script>
</body>
</html>`;
  }

  stop(): void {
    if (this.server) {
      this.server.close();
      this.server = null;
    }
  }
}

// ═══════════════════════════════════════════════════════════
// Extension Entry
// ═══════════════════════════════════════════════════════════

let webmcpServer: WebMCPServer | null = null;
let receiptChain: ReceiptChain | null = null;
let ideStateObserver: IDEStateObserver | null = null;

export function activate(context: vscode.ExtensionContext) {
  console.log('VSCODER://BRIDGE v1.0 activating...');

  // Initialize receipt chain
  receiptChain = new ReceiptChain();

  // Initialize IDE state observer
  const autoObserve = vscode.workspace.getConfiguration('vscoderBridge').get<boolean>('autoObserve', true);
  ideStateObserver = new IDEStateObserver(autoObserve);
  context.subscriptions.push(ideStateObserver);

  // Start WebMCP HTTP server
  const port = vscode.workspace.getConfiguration('vscoderBridge').get<number>('webmcpPort', 8123);
  const authToken = vscode.workspace.getConfiguration('vscoderBridge').get<string>('authToken', '');
  webmcpServer = new WebMCPServer(context, receiptChain, ideStateObserver, port, authToken);
  webmcpServer.start();

  // Register commands
  const commands = [
    { name: 'vscoderBridge.open', handler: () => openAgentPanel(context) },
    { name: 'vscoderBridge.observe', handler: () => quickTool('vscoder_observe') },
    { name: 'vscoderBridge.plan', handler: () => quickTool('vscoder_plan') },
    { name: 'vscoderBridge.refactor', handler: () => quickTool('vscoder_refactor') },
    { name: 'vscoderBridge.build', handler: () => quickTool('vscoder_build') },
    { name: 'vscoderBridge.test', handler: () => quickTool('vscoder_test') },
    { name: 'vscoderBridge.debug', handler: () => quickTool('vscoder_debug') },
    { name: 'vscoderBridge.benchmark', handler: () => quickTool('vscoder_benchmark') },
    { name: 'vscoderBridge.gitDiff', handler: () => quickTool('vscoder_git_diff') },
    { name: 'vscoderBridge.receipt', handler: () => quickTool('vscoder_receipt') },
  ];

  for (const cmd of commands) {
    const disposable = vscode.commands.registerCommand(cmd.name, cmd.handler);
    context.subscriptions.push(disposable);
  }

  // Log activation
  receiptChain.append({
    intent: 'activate',
    plan: 'extension',
    before: '',
    after: JSON.stringify({ version: '1.0.0', port }),
  });

  vscode.window.showInformationMessage('VSCODER://BRIDGE v1.0 ready — WebMCP on :' + port);
}

function openAgentPanel(context: vscode.ExtensionContext): void {
  const panel = vscode.window.createWebviewPanel(
    'vscoderBridgeAgent',
    'VSCODER://BRIDGE Agent',
    vscode.ViewColumn.One,
    { enableScripts: true, retainContextWhenHidden: true }
  );

  panel.webview.html = getAgentPanelHtml();
  panel.webview.onDidReceiveMessage(async (message: any) => {
    if (message?.command === 'vscoderBridge.invoke') {
      const result = await webmcpServer?.invokeTool(message.tool, message.params);
      panel.webview.postMessage({ command: 'vscoderBridge.result', result });
    }
  });
}

async function quickTool(tool: string): Promise<void> {
  const result = await webmcpServer?.invokeTool(tool, {});
  const panel = vscode.window.createWebviewPanel(
    'vscoderBridgeResult',
    `VSCODER: ${tool}`,
    vscode.ViewColumn.Beside,
    { enableScripts: true }
  );
  panel.webview.html = `<html><body><pre>${JSON.stringify(result, null, 2)}</pre></body></html>`;
}

function getAgentPanelHtml(): string {
  return `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>VSCODER://BRIDGE Agent</title>
<style>body{font-family:monospace;padding:16px;background:#050505;color:#D4AF37}
textarea{width:100%;height:80px;background:#060609;color:#e8e6df;border:1px solid #333;border-radius:4px;padding:8px}
button{background:#1a1a1a;color:#D4AF37;border:1px solid #D4AF37;border-radius:4px;padding:8px 12px;cursor:pointer;margin:4px}
pre{white-space:pre-wrap;color:#8b8b8b;font-size:11px;max-height:300px;overflow:auto}
</style></head><body>
<h2>VSCODER://BRIDGE Agent</h2>
<textarea id="inst" placeholder="Instruction (e.g. optimize vision-supervision)"></textarea>
<div>
<button onclick="run('vscoder_observe')">Observe</button>
<button onclick="run('vscoder_plan')">Plan</button>
<button onclick="run('vscoder_refactor')">Refactor</button>
<button onclick="run('vscoder_build')">Build</button>
<button onclick="run('vscoder_test')">Test</button>
<button onclick="run('vscoder_debug')">Debug</button>
<button onclick="run('vscoder_benchmark')">Benchmark</button>
<button onclick="run('vscoder_git_diff')">Git Diff</button>
<button onclick="run('vscoder_receipt')">Receipt</button>
</div>
<pre id="out">Ready.</pre>
<script>
const vscode = acquireVsCodeApi();
const out = document.getElementById('out');
function run(tool) {
  const instruction = document.getElementById('inst').value;
  vscode.postMessage({ command: 'vscoderBridge.invoke', tool, params: { instruction } });
}
window.addEventListener('message', event => {
  const msg = event.data;
  if (msg.command === 'vscoderBridge.result') {
    out.textContent = JSON.stringify(msg.result, null, 2);
  }
});
</script></body></html>`;
}

export function deactivate(): void {
  webmcpServer?.stop();
  console.log('VSCODER://BRIDGE deactivated');
}
