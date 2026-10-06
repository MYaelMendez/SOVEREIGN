import * as vscode from 'vscode';
import * as path from 'path';
import * as crypto from 'crypto';
import * as http from 'http';
import * as fs from 'fs';
import { execSync } from 'child_process';

// ═══════════════════════════════════════════════════════════
// VSCODER:// v0.1 — VS Code-native autonomous engineering agent
// ═══════════════════════════════════════════════════════════

// ── Receipt System with SHA-256 Hash Chain ──

interface ReceiptEntry {
  seq: number;
  timestamp: string;
  action: string;
  input: string;
  output: string;
  prevHash: string;
  hash: string;
}

class ReceiptChain {
  private chain: ReceiptEntry[] = [];
  private readonly storagePath: string;

  constructor(context: vscode.ExtensionContext) {
    this.storagePath = path.join(context.globalStorageUri.fsPath, 'receipts.json');
    this.load();
  }

  private load(): void {
    try {
      if (fs.existsSync(this.storagePath)) {
        const raw = fs.readFileSync(this.storagePath, 'utf8');
        this.chain = JSON.parse(raw);
      }
    } catch {
      this.chain = [];
    }
  }

  private save(): void {
    try {
      fs.mkdirSync(path.dirname(this.storagePath), { recursive: true });
      fs.writeFileSync(this.storagePath, JSON.stringify(this.chain, null, 2), 'utf8');
    } catch (e) {
      console.error('VSCODER: failed to save receipts:', e);
    }
  }

  private computeHash(entry: Omit<ReceiptEntry, 'hash'>): string {
    const data = JSON.stringify({
      seq: entry.seq,
      timestamp: entry.timestamp,
      action: entry.action,
      input: entry.input,
      output: entry.output,
      prevHash: entry.prevHash,
    });
    return crypto.createHash('sha256').update(data).digest('hex');
  }

  add(action: string, input: string, output: string): ReceiptEntry {
    const prevHash = this.chain.length > 0
      ? this.chain[this.chain.length - 1].hash
      : 'genesis';
    const entry: Omit<ReceiptEntry, 'hash'> = {
      seq: this.chain.length + 1,
      timestamp: new Date().toISOString(),
      action,
      input: input.slice(0, 500),
      output: output.slice(0, 500),
      prevHash,
    };
    const hash = this.computeHash(entry);
    const full: ReceiptEntry = { ...entry, hash };
    this.chain.push(full);
    this.save();
    return full;
  }

  getChain(): ReceiptEntry[] {
    return [...this.chain];
  }

  getLast(): ReceiptEntry | undefined {
    return this.chain.length > 0 ? this.chain[this.chain.length - 1] : undefined;
  }

  verify(): boolean {
    for (let i = 0; i < this.chain.length; i++) {
      const entry = this.chain[i];
      const { hash, ...rest } = entry;
      const computed = this.computeHash(rest);
      if (computed !== hash) return false;
      if (i > 0 && entry.prevHash !== this.chain[i - 1].hash) return false;
    }
    return true;
  }
}

// ── WebMCP HTTP Server ──

class WebMCPServer {
  private server: http.Server | null = null;
  private port: number;
  private receipts: ReceiptChain;
  private extensionContext: vscode.ExtensionContext;

  constructor(context: vscode.ExtensionContext, receipts: ReceiptChain, port: number = 8123) {
    this.extensionContext = context;
    this.receipts = receipts;
    this.port = port;
  }

  start(): void {
    if (this.server) return;

    this.server = http.createServer((req, res) => {
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

      if (req.method === 'OPTIONS') {
        res.writeHead(204);
        res.end();
        return;
      }

      const url = req.url || '/';

      if (url === '/' || url === '/index.html') {
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(this.getWebviewHtml());
        return;
      }

      if (url === '/api/receipts') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          chain: this.receipts.getChain(),
          valid: this.receipts.verify(),
          count: this.receipts.getChain().length,
        }));
        return;
      }

      if (url === '/api/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok', version: '0.1.0', tools: this.getToolNames() }));
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
      console.log(`VSCODER: WebMCP server listening on :${this.port}`);
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
    const workspaceFolders = vscode.workspace.workspaceFolders || [];
    const editors = vscode.window.visibleTextEditors.map(e => ({
      path: e.document.uri.fsPath,
      language: e.document.languageId,
      lineCount: e.document.lineCount,
      selection: {
        start: { line: e.selection.start.line, character: e.selection.start.character },
        end: { line: e.selection.end.line, character: e.selection.end.character },
      },
    }));

    const result = {
      workspace: workspaceFolders.map(f => f.uri.fsPath),
      editors,
      timestamp: new Date().toISOString(),
    };

    this.receipts.add('observe', JSON.stringify(params), JSON.stringify(result));
    return result;
  }

  private async toolPlan(params: any): Promise<any> {
    const instruction = params.instruction || 'optimize workspace';
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';

    // Use LSP to gather symbols from active editor
    const editor = vscode.window.activeTextEditor;
    let symbols: any[] = [];
    if (editor) {
      try {
        const doc = editor.document;
        const syms = await vscode.commands.executeCommand<vscode.SymbolInformation[]>(
          'vscode.executeDocumentSymbolProvider', doc.uri
        );
        symbols = (syms || []).map(s => ({
          name: s.name,
          kind: vscode.SymbolKind[s.kind],
          location: s.location?.uri?.fsPath,
        }));
      } catch {
        // LSP not available
      }
    }

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
      timestamp: new Date().toISOString(),
    };

    this.receipts.add('plan', instruction, JSON.stringify(plan));
    return plan;
  }

  private async toolRefactor(params: any): Promise<any> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      return { error: 'No active editor' };
    }

    const doc = editor.document;
    const position = editor.selection.active;
    const refactorKind = params.kind || 'rename';
    const newName = params.newName || 'refactoredSymbol';

    let result: any = { kind: refactorKind, applied: false };

    try {
      if (refactorKind === 'rename') {
        // Use LSP Rename Symbol
        const workspaceEdit = await vscode.commands.executeCommand<vscode.WorkspaceEdit>(
          'vscode.executeDocumentRenameProvider',
          doc.uri,
          position,
          newName
        );
        if (workspaceEdit) {
          const success = await vscode.workspace.applyEdit(workspaceEdit);
          result = { kind: 'rename', applied: success, newName, changes: workspaceEdit.size };
        }
      } else if (refactorKind === 'findReferences') {
        const refs = await vscode.commands.executeCommand<vscode.Location[]>(
          'vscode.executeReferenceProvider',
          doc.uri,
          position
        );
        result = { kind: 'findReferences', count: refs?.length || 0, references: refs?.slice(0, 20) };
      } else if (refactorKind === 'codeAction') {
        const actions = await vscode.commands.executeCommand<vscode.CodeAction[]>(
          'vscode.executeCodeActionProvider',
          doc.uri,
          editor.selection
        );
        result = { kind: 'codeAction', count: actions?.length || 0, actions: actions?.map(a => a.title) };
      }
    } catch (e: unknown) {
      result = { kind: refactorKind, error: (e instanceof Error ? e.message : String(e)) };
    }

    this.receipts.add('refactor', JSON.stringify(params), JSON.stringify(result));
    return result;
  }

  private async toolBuild(params: any): Promise<any> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    const buildCmd = params.command || 'python -m py_compile';

    let result: any;
    try {
      const output = execSync(buildCmd, { cwd: workspaceRoot, timeout: 30000, encoding: 'utf8' });
      result = { success: true, output: output.slice(0, 2000) };
    } catch (e: unknown) {
      result = { success: false, error: (e instanceof Error ? e.message : String(e)), stdout: ((e as Error & { stdout?: string }).stdout ?? "").slice(0, 2000), stderr: ((e as Error & { stderr?: string }).stderr ?? "").slice(0, 2000) };
    }

    this.receipts.add('build', buildCmd, JSON.stringify(result));
    return result;
  }

  private async toolTest(params: any): Promise<any> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    const testCmd = params.command || 'python -m pytest --tb=short -q';

    let result: any;
    try {
      const output = execSync(testCmd, { cwd: workspaceRoot, timeout: 60000, encoding: 'utf8' });
      result = { success: true, output: output.slice(0, 3000) };
    } catch (e: unknown) {
      result = { success: false, error: (e instanceof Error ? e.message : String(e)), stdout: ((e as Error & { stdout?: string }).stdout ?? "").slice(0, 3000), stderr: ((e as Error & { stderr?: string }).stderr ?? "").slice(0, 3000) };
    }

    this.receipts.add('test', testCmd, JSON.stringify(result));
    return result;
  }

  private async toolDebug(params: any): Promise<any> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    const debugConfig = params.config || {
      type: 'python',
      name: 'VSCODER Debug',
      request: 'launch',
      program: '${file}',
      console: 'integratedTerminal',
    };

    try {
      const success = await vscode.debug.startDebugging(
        vscode.workspace.workspaceFolders?.[0],
        debugConfig
      );
      const result = { success, config: debugConfig };
      this.receipts.add('debug', JSON.stringify(params), JSON.stringify(result));
      return result;
    } catch (e: unknown) {
      const result = { success: false, error: (e instanceof Error ? e.message : String(e)) };
      this.receipts.add('debug', JSON.stringify(params), JSON.stringify(result));
      return result;
    }
  }

  private async toolBenchmark(params: any): Promise<any> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    const benchCmd = params.command || 'python -m pytest --benchmark-only --benchmark-json=benchmark.json';

    let result: any;
    try {
      const output = execSync(benchCmd, { cwd: workspaceRoot, timeout: 120000, encoding: 'utf8' });
      result = { success: true, output: output.slice(0, 3000) };
    } catch (e: unknown) {
      result = { success: false, error: (e instanceof Error ? e.message : String(e)), stdout: ((e as Error & { stdout?: string }).stdout ?? "").slice(0, 3000) };
    }

    this.receipts.add('benchmark', benchCmd, JSON.stringify(result));
    return result;
  }

  private async toolGitDiff(params: any): Promise<any> {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';

    let result: any;
    try {
      const diff = execSync('git diff --stat', { cwd: workspaceRoot, timeout: 10000, encoding: 'utf8' });
      const status = execSync('git status --short', { cwd: workspaceRoot, timeout: 10000, encoding: 'utf8' });
      const log = execSync('git log --oneline -5', { cwd: workspaceRoot, timeout: 10000, encoding: 'utf8' });
      result = { diff, status, log, hasChanges: diff.trim().length > 0 };
    } catch (e: unknown) {
      result = { error: (e instanceof Error ? e.message : String(e)), isGitRepo: false };
    }

    this.receipts.add('git_diff', JSON.stringify(params), JSON.stringify(result));
    return result;
  }

  private toolReceipt(params: any): any {
    const chain = this.receipts.getChain();
    const valid = this.receipts.verify();
    const last = this.receipts.getLast();

    return {
      chain,
      valid,
      count: chain.length,
      last,
      timestamp: new Date().toISOString(),
    };
  }

  private getWebviewHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>VSCODER:// v0.1</title>
<style>
:root{--void:#050505;--panel:#0a0a0f;--gold:#D4AF37;--gold2:#f0d487;--emerald:#00ff9d;--cyan:#00eaff;--violet:#8c72ff;--orange:#ff9a4d;--ink:#e8e6df;--muted:#6f6a5c;--line:rgba(212,175,55,.22);--mono:"JetBrains Mono",ui-monospace,monospace;--display:"Orbitron",sans-serif;--error:#ff7b72;}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;overflow:hidden;background:var(--void);color:var(--ink);font-family:var(--mono)}
#app{display:grid;grid-template-rows:auto 1fr auto;height:100vh;padding:12px;gap:10px}
.header{display:flex;align-items:baseline;gap:14px;border-bottom:1px solid var(--line);padding-bottom:10px}
.title{font-size:18px;font-weight:700;color:var(--gold);letter-spacing:.08em}
.subtitle{font-size:11px;color:var(--muted);letter-spacing:.12em}
.main{display:grid;grid-template-columns:1fr 1fr;gap:10px;min-height:0}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;overflow:auto}
.panel h2{font-size:12px;color:var(--gold);margin-bottom:8px;letter-spacing:.06em}
.panel pre{font-size:10px;color:var(--muted);white-space:pre-wrap;word-break:break-word;max-height:200px;overflow:auto}
.footer{display:flex;gap:8px;align-items:center;border-top:1px solid var(--line);padding-top:8px}
.btn{background:linear-gradient(135deg,rgba(212,175,55,.15),rgba(0,255,163,.08));border:1px solid rgba(212,175,55,.65);color:var(--gold);padding:8px 12px;border-radius:8px;font:inherit;font-size:11px;cursor:pointer}
.btn:hover{background:rgba(212,175,55,.2)}
.btn.secondary{border-color:var(--line);color:var(--muted)}
.status{font-size:10px;color:var(--emerald);display:flex;align-items:center;gap:6px}
.status::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--emerald);box-shadow:0 0 6px var(--emerald)}
#log{font-size:9px;color:var(--muted);max-height:120px;overflow:auto;white-space:pre-wrap}
.err{color:var(--error)}
input,textarea{width:100%;background:#060609;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:8px;font:inherit;font-size:11px;margin-bottom:8px}
</style>
</head>
<body>
<div id="app">
  <div class="header">
    <div class="title">VSCODER://</div>
    <div class="subtitle">v0.1 · VS Code-native autonomous engineering agent</div>
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
    </div>
    <div class="panel">
      <h2>OUTPUT</h2>
      <pre id="output">Awaiting instruction...</pre>
    </div>
  </div>
  <div class="footer">
    <span style="font-size:10px;color:var(--muted)">WebMCP: :8123 · LSP: active · Receipts: <span id="receiptCount">0</span></span>
  </div>
  <div id="log"></div>
</div>
<script>
const logEl = document.getElementById('log');
const outputEl = document.getElementById('output');
const statusEl = document.getElementById('status');
const receiptCountEl = document.getElementById('receiptCount');
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
  } catch(e) {}
}

updateReceiptCount();
log('VSCODER:// v0.1 initialized');
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

// ── Extension Entry ──

let webmcpServer: WebMCPServer | null = null;
let receiptChain: ReceiptChain | null = null;

export function activate(context: vscode.ExtensionContext) {
  console.log('VSCODER:// v0.1 activating...');

  // Initialize receipt chain
  receiptChain = new ReceiptChain(context);

  // Start WebMCP HTTP server
  const port = vscode.workspace.getConfiguration('vscoder').get<number>('webmcpPort', 8123);
  webmcpServer = new WebMCPServer(context, receiptChain, port);
  webmcpServer.start();

  // Register commands
  const commands = [
    { name: 'vscoder.open', handler: () => openAgentPanel(context) },
    { name: 'vscoder.observe', handler: () => quickTool('vscoder_observe') },
    { name: 'vscoder.plan', handler: () => quickTool('vscoder_plan') },
    { name: 'vscoder.refactor', handler: () => quickTool('vscoder_refactor') },
    { name: 'vscoder.build', handler: () => quickTool('vscoder_build') },
    { name: 'vscoder.test', handler: () => quickTool('vscoder_test') },
    { name: 'vscoder.debug', handler: () => quickTool('vscoder_debug') },
    { name: 'vscoder.benchmark', handler: () => quickTool('vscoder_benchmark') },
    { name: 'vscoder.gitDiff', handler: () => quickTool('vscoder_git_diff') },
    { name: 'vscoder.receipt', handler: () => quickTool('vscoder_receipt') },
  ];

  for (const cmd of commands) {
    const disposable = vscode.commands.registerCommand(cmd.name, cmd.handler);
    context.subscriptions.push(disposable);
  }

  // Log activation
  receiptChain.add('activate', 'extension', JSON.stringify({ version: '0.1.0', port }));

  vscode.window.showInformationMessage('VSCODER:// v0.1 ready — WebMCP on :' + port);
}

function openAgentPanel(context: vscode.ExtensionContext): void {
  const panel = vscode.window.createWebviewPanel(
    'vscoderAgent',
    'VSCODER:// Agent',
    vscode.ViewColumn.One,
    { enableScripts: true, retainContextWhenHidden: true }
  );

  panel.webview.html = getAgentPanelHtml();
  panel.webview.onDidReceiveMessage(async (message: any) => {
    if (message?.command === 'vscoder.invoke') {
      const result = await webmcpServer?.invokeTool(message.tool, message.params);
      panel.webview.postMessage({ command: 'vscoder.result', result });
    }
  });
}

async function quickTool(tool: string): Promise<void> {
  const result = await webmcpServer?.invokeTool(tool, {});
  const panel = vscode.window.createWebviewPanel(
    'vscoderResult',
    `VSCODER: ${tool}`,
    vscode.ViewColumn.Beside,
    { enableScripts: true }
  );
  panel.webview.html = `<html><body><pre>${JSON.stringify(result, null, 2)}</pre></body></html>`;
}

function getAgentPanelHtml(): string {
  return `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>VSCODER:// Agent</title>
<style>body{font-family:monospace;padding:16px;background:#050505;color:#D4AF37}
textarea{width:100%;height:80px;background:#060609;color:#e8e6df;border:1px solid #333;border-radius:4px;padding:8px}
button{background:#1a1a1a;color:#D4AF37;border:1px solid #D4AF37;border-radius:4px;padding:8px 12px;cursor:pointer;margin:4px}
pre{white-space:pre-wrap;color:#8b8b8b;font-size:11px;max-height:300px;overflow:auto}
</style></head><body>
<h2>VSCODER:// Agent</h2>
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
  vscode.postMessage({ command: 'vscoder.invoke', tool, params: { instruction } });
}
window.addEventListener('message', event => {
  const msg = event.data;
  if (msg.command === 'vscoder.result') {
    out.textContent = JSON.stringify(msg.result, null, 2);
  }
});
</script></body></html>`;
}

export function deactivate(): void {
  webmcpServer?.stop();
  console.log('VSCODER:// deactivated');
}