import * as vscode from 'vscode';
import * as path from 'path';
import type { AgentContext, StateName } from './stateMachine.js';
import { STATE_ORDER, nextState } from './stateMachine.js';
import { ReceiptChain } from './receipts.js';
import { AuthorityPolicy } from './policy.js';
import { CAPABILITIES, getCapability } from './capabilities.js';

export function activate(context: vscode.ExtensionContext) {
  const openCmd = vscode.commands.registerCommand('pcCode.open', async () => {
    const panel = vscode.window.createWebviewPanel(
      'pcCode',
      'PC://CODE — Sovereign Agent',
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [
          vscode.Uri.file(path.join(context.extensionPath, 'out')),
          vscode.Uri.file(path.join(context.extensionPath, 'webview')),
          vscode.Uri.file(path.join(context.extensionPath, 'vendor')),
        ],
      }
    );

    panel.webview.html = getWebviewContent(context, panel);

    panel.webview.onDidReceiveMessage(async (message: any) => {
      const cmd: string = message?.command || '';
      if (cmd === 'pcCode.run') {
        const instruction = String(message.instruction || 'inspect this workspace');
        await runAgentLoop(panel, instruction);
      } else if (cmd === 'pcCode.inspect') {
        await runAgentLoop(panel, 'inspect this workspace');
      } else if (cmd === 'pcCode.reset') {
        await runAgentLoop(panel, 'inspect this workspace', true);
      }
    });
  });

  context.subscriptions.push(openCmd);
}

async function runAgentLoop(panel: vscode.WebviewPanel, instruction: string, reset: boolean = false) {
  const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || 'C:/æ';
  const receiptChain = new ReceiptChain();
  const policy = new AuthorityPolicy();

  const ctx: AgentContext = {
    workspacePath,
    instruction,
    currentState: 'IDLE',
    history: [],
    receipts: [],
    policy,
    receiptChain,
  };

  const STATE_CAPABILITY: Record<StateName, string> = {
    IDLE: 'workspace_inspect',
    OBSERVE: 'workspace_inspect',
    PLAN: 'symbol_find',
    VALIDATE_PLAN: 'diagnostics_read',
    EXECUTE: 'symbol_references',
    DIAGNOSTICS: 'diagnostics_read',
    BUILD: 'build_run',
    TEST: 'test_run',
    REVIEW_DIFF: 'git_diff',
    COMPLETE: 'receipt_verify',
  };

  panel.webview.postMessage({ command: 'pcCode.state', state: 'IDLE', instruction });

  for (const state of STATE_ORDER) {
    ctx.currentState = state;
    const capName = STATE_CAPABILITY[state];
    const capability = getCapability(capName);

    if (!capability) {
      panel.webview.postMessage({ command: 'pcCode.error', error: `Unknown capability: ${capName}` });
      continue;
    }

    if (!policy.check(capability)) {
      panel.webview.postMessage({
        command: 'pcCode.skipped',
        state,
        capability: capName,
        reason: `Effect class ${capability.effect} denied by policy`,
      });
      continue;
    }

    panel.webview.postMessage({
      command: 'pcCode.progress',
      state,
      capability: capName,
      effect: capability.effect,
    });

    const result = await capability.execute(ctx);
    const output = result.success
      ? (typeof result.data === 'string' ? result.data : JSON.stringify(result.data, null, 2))
      : `ERROR: ${result.error}`;

    const receipt = receiptChain.addReceipt(
      capName,
      state,
      capability.effect,
      instruction,
      output
    );

    ctx.history.push({
      from: state,
      to: nextState(state) || state,
      capability: capName,
      effect: capability.effect,
      timestamp: receipt.timestamp,
      receiptHash: receipt.hash,
    });

    panel.webview.postMessage({
      command: 'pcCode.step',
      state,
      capability: capName,
      effect: capability.effect,
      success: result.success,
      output: output.slice(0, 6000),
      receipt: {
        index: receipt.index,
        hash: receipt.hash,
        prevHash: receipt.prevHash,
        timestamp: receipt.timestamp,
      },
    });
  }

  const chainValid = receiptChain.verify();
  panel.webview.postMessage({
    command: 'pcCode.complete',
    totalReceipts: receiptChain.length,
    chainValid,
    lastHash: receiptChain.getLastHash(),
    history: ctx.history,
  });
}

function getWebviewContent(context: vscode.ExtensionContext, panel: vscode.WebviewPanel): string {
  const scriptPath = panel.webview.asWebviewUri(
    vscode.Uri.file(path.join(context.extensionPath, 'out', 'webview.js'))
  ).toString();

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>PC://CODE — Sovereign Agent</title>
<style>
  :root{
    --void:#050505;--gold:#D4AF37;--gold2:#f0d487;--emerald:#00ff9d;
    --cyan:#00eaff;--violet:#8c72ff;--orange:#ff9a4d;--red:#ff4d4d;
    --ink:#e8e6df;--muted:#6f6a5c;--line:rgba(212,175,55,.22);
    --mono:"JetBrains Mono",ui-monospace,monospace;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:100%;height:100%;overflow:hidden;background:var(--void);color:var(--ink);font-family:var(--mono);font-size:13px}
  #app{display:flex;flex-direction:column;height:100%;padding:12px;gap:10px}
  header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:8px}
  header h1{font-size:16px;color:var(--gold);letter-spacing:.12em}
  header .status{font-size:11px;color:var(--muted)}
  header .status .live{color:var(--emerald)}
  .controls{display:flex;gap:8px;align-items:center}
  .controls input{flex:1;background:rgba(8,8,7,.85);border:1px solid var(--line);color:var(--ink);padding:6px 10px;font-family:var(--mono);font-size:12px;outline:none}
  .controls input:focus{border-color:var(--gold)}
  .controls button{background:rgba(212,175,55,.12);border:1px solid var(--gold);color:var(--gold);padding:6px 14px;cursor:pointer;font-family:var(--mono);font-size:11px;letter-spacing:.08em;transition:all .2s}
  .controls button:hover{background:rgba(212,175,55,.25);color:var(--gold2)}
  .controls button:disabled{opacity:.4;cursor:not-allowed}
  .main{flex:1;display:flex;gap:10px;overflow:hidden}
  .panel{flex:1;overflow-y:auto;border:1px solid var(--line);background:rgba(8,8,7,.6);padding:10px}
  .panel h2{font-size:11px;color:var(--muted);letter-spacing:.12em;margin-bottom:8px;text-transform:uppercase}
  .state-track{display:flex;flex-direction:column;gap:4px;margin-bottom:12px}
  .state-node{display:flex;align-items:center;gap:8px;padding:4px 8px;border:1px solid transparent;font-size:11px;transition:all .3s}
  .state-node.active{border-color:var(--gold);background:rgba(212,175,55,.08)}
  .state-node.done{color:var(--emerald)}
  .state-node.skipped{color:var(--muted);opacity:.5}
  .state-node .dot{width:8px;height:8px;border-radius:50%;border:1px solid var(--muted)}
  .state-node.active .dot{background:var(--gold);border-color:var(--gold);box-shadow:0 0 6px var(--gold)}
  .state-node.done .dot{background:var(--emerald);border-color:var(--emerald)}
  .state-node .name{width:120px;font-weight:600}
  .state-node .cap{color:var(--muted);font-size:10px}
  .state-node .effect{margin-left:auto;font-size:9px;padding:1px 5px;border:1px solid}
  .effect.LOCAL{color:var(--cyan);border-color:var(--cyan)}
  .effect.DURABLE{color:var(--orange);border-color:var(--orange)}
  .effect.EXTERNAL{color:var(--red);border-color:var(--red)}
  .log{display:flex;flex-direction:column;gap:4px}
  .log-entry{font-size:10px;padding:4px 6px;border-left:2px solid var(--line);padding-left:8px}
  .log-entry.success{border-color:var(--emerald)}
  .log-entry.error{border-color:var(--red);color:var(--red)}
  .log-entry.info{border-color:var(--cyan)}
  .log-entry .meta{color:var(--muted);font-size:9px}
  .log-entry .output{margin-top:2px;white-space:pre-wrap;word-break:break-word;max-height:200px;overflow-y:auto;color:var(--ink)}
  .receipts{display:flex;flex-direction:column;gap:4px}
  .receipt{border:1px solid var(--line);padding:6px;font-size:10px}
  .receipt .header{display:flex;justify-content:space-between;color:var(--gold);margin-bottom:4px}
  .receipt .hash{font-size:9px;color:var(--muted);word-break:break-all}
  .receipt .verified{color:var(--emerald)}
  .empty{color:var(--muted);font-size:11px;text-align:center;padding:20px}
  .progress-bar{width:100%;height:2px;background:var(--line);margin:8px 0}
  .progress-bar .fill{height:100%;background:var(--gold);transition:width .3s}
  .chain-status{padding:6px;border:1px solid var(--line);font-size:11px;margin-bottom:8px}
  .chain-status.valid{border-color:var(--emerald);color:var(--emerald)}
  .chain-status.invalid{border-color:var(--red);color:var(--red)}
  ::-webkit-scrollbar{width:4px}
  ::-webkit-scrollbar-track{background:var(--void)}
  ::-webkit-scrollbar-thumb{background:var(--line)}
</style>
</head>
<body>
<div id="app">
  <header>
    <h1>PC://CODE</h1>
    <div class="status" id="status"><span class="idle">IDLE</span></div>
  </header>
  <div class="controls">
    <input id="instruction" placeholder="inspect this workspace" value="inspect this workspace"/>
    <button id="runBtn" onclick="run()">RUN</button>
    <button id="resetBtn" onclick="reset()">RESET</button>
  </div>
  <div class="progress-bar"><div class="fill" id="progressFill" style="width:0%"></div></div>
  <div class="main">
    <div class="panel" id="statePanel">
      <h2>State Machine</h2>
      <div class="state-track" id="stateTrack"></div>
      <div class="chain-status" id="chainStatus">Chain: empty</div>
      <h2>Receipts</h2>
      <div class="receipts" id="receipts"></div>
    </div>
    <div class="panel" id="logPanel">
      <h2>Execution Log</h2>
      <div class="log" id="log"></div>
    </div>
  </div>
</div>
<script>
  const STATES = ${JSON.stringify(STATE_ORDER)};
  const CAP_MAP = ${JSON.stringify({
    IDLE: 'workspace_inspect',
    OBSERVE: 'workspace_inspect',
    PLAN: 'symbol_find',
    VALIDATE_PLAN: 'diagnostics_read',
    EXECUTE: 'symbol_references',
    DIAGNOSTICS: 'diagnostics_read',
    BUILD: 'build_run',
    TEST: 'test_run',
    REVIEW_DIFF: 'git_diff',
    COMPLETE: 'receipt_verify',
  })};

  function renderStates(activeState, doneStates) {
    const track = document.getElementById('stateTrack');
    track.innerHTML = STATES.map(s => {
      const cap = CAP_MAP[s] || '';
      const effect = cap.includes('build') || cap.includes('test') ? 'DURABLE' :
                     cap.includes('git') || cap.includes('receipt') ? 'LOCAL' : 'LOCAL';
      const cls = s === activeState ? 'active' : doneStates.has(s) ? 'done' : '';
      const dot = s === activeState ? 'active' : doneStates.has(s) ? 'done' : '';
      return '<div class="state-node ' + cls + '">' +
        '<span class="dot ' + dot + '"></span>' +
        '<span class="name">' + s + '</span>' +
        '<span class="cap">' + cap + '</span>' +
        '<span class="effect ' + effect + '">' + effect + '</span>' +
        '</div>';
    }).join('');
  }

  function addLog(type, meta, output) {
    const log = document.getElementById('log');
    const entry = document.createElement('div');
    entry.className = 'log-entry ' + type;
    entry.innerHTML = '<div class="meta">' + meta + '</div>' +
      (output ? '<div class="output">' + escapeHtml(output.slice(0, 2000)) + '</div>' : '');
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
  }

  function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function updateProgress(current, total) {
    document.getElementById('progressFill').style.width = (current / total * 100) + '%';
  }

  function setStatus(text, cls) {
    document.getElementById('status').innerHTML = '<span class="' + (cls||'idle') + '">' + text + '</span>';
  }

  function run() {
    const instr = document.getElementById('instruction').value || 'inspect this workspace';
    document.getElementById('log').innerHTML = '';
    document.getElementById('receipts').innerHTML = '';
    renderStates('IDLE', new Set());
    updateProgress(0, STATES.length);
    setStatus('RUNNING', 'live');
    acquireVsCodeApi().postMessage({ command: 'pcCode.run', instruction: instr });
  }

  function reset() {
    document.getElementById('log').innerHTML = '';
    document.getElementById('receipts').innerHTML = '';
    document.getElementById('chainStatus').className = 'chain-status';
    document.getElementById('chainStatus').textContent = 'Chain: empty';
    renderStates('IDLE', new Set());
    updateProgress(0, STATES.length);
    setStatus('IDLE', 'idle');
    acquireVsCodeApi().postMessage({ command: 'pcCode.reset' });
  }

  window.addEventListener('message', event => {
    const msg = event.data;
    if (!msg || !msg.command) return;
    switch (msg.command) {
      case 'pcCode.state':
        setStatus(msg.state, 'live');
        break;
      case 'pcCode.progress':
        addLog('info', msg.state + ' → ' + msg.capability + ' [' + msg.effect + ']', '');
        renderStates(msg.state, new Set());
        break;
      case 'pcCode.step': {
        const done = new Set();
        for (const s of STATES) {
          if (STATES.indexOf(s) < STATES.indexOf(msg.state)) done.add(s);
        }
        done.add(msg.state);
        renderStates(msg.state, done);
        updateProgress(STATES.indexOf(msg.state) + 1, STATES.length);
        addLog(msg.success ? 'success' : 'error',
          msg.state + ' → ' + msg.capability + ' [' + msg.effect + ']',
          msg.output);
        const rc = document.getElementById('receipts');
        const r = document.createElement('div');
        r.className = 'receipt';
        r.innerHTML = '<div class="header"><span>#' + msg.receipt.index + ' ' + msg.capability + '</span><span class="verified">✓</span></div>' +
          '<div class="hash">' + msg.receipt.hash.slice(0, 32) + '...</div>';
        rc.appendChild(r);
        break;
      }
      case 'pcCode.skipped':
        addLog('info', msg.state + ' SKIPPED: ' + msg.reason, '');
        break;
      case 'pcCode.error':
        addLog('error', 'ERROR', msg.error);
        break;
      case 'pcCode.complete': {
        setStatus('COMPLETE', 'idle');
        updateProgress(STATES.length, STATES.length);
        const cs = document.getElementById('chainStatus');
        cs.className = 'chain-status ' + (msg.chainValid ? 'valid' : 'invalid');
        cs.textContent = 'Chain: ' + (msg.chainValid ? 'VALID' : 'INVALID') + ' — ' + msg.totalReceipts + ' receipts — last: ' + msg.lastHash.slice(0, 24) + '...';
        addLog('success', 'LOOP COMPLETE', 'Total receipts: ' + msg.totalReceipts + '\\nChain valid: ' + msg.chainValid);
        break;
      }
    }
  });

  renderStates('IDLE', new Set());
</script>
</body>
</html>`;
}

export function deactivate() {}
