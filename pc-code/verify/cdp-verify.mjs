/**
 * PC://CODE v0.1 — CDP Verification Script
 * Uses Node 26 built-in WebSocket to drive headless Chrome via CDP.
 * Verifies: page loads, state machine renders, agent loop runs, receipt chain validates.
 */

import { spawn } from 'child_process';
import { setTimeout as sleep } from 'timers/promises';
import * as http from 'http';
import * as fs from 'fs';
import * as path from 'path';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9222;
const HTTP_PORT = 8124;
const PCODE_DIR = 'C:\\æ\\pc-code';

let chrome;
let ws;
let msgId = 0;
const pending = new Map();

function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++msgId;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}

function startHttpServer() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const url = req.url === '/' ? '/webview/pc-code.html' : req.url;
      const filePath = path.join(PCODE_DIR, url);
      try {
        const content = fs.readFileSync(filePath);
        const ext = path.extname(filePath);
        const mime = ext === '.html' ? 'text/html' : ext === '.js' ? 'application/javascript' : ext === '.css' ? 'text/css' : 'text/plain';
        res.writeHead(200, { 'Content-Type': mime });
        res.end(content);
      } catch {
        res.writeHead(404);
        res.end('Not found');
      }
    });
    server.listen(HTTP_PORT, () => resolve(server));
  });
}

async function startChrome() {
  chrome = spawn(CHROME, [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--user-data-dir=' + path.join(PCODE_DIR, '.chrome-profile'),
    'about:blank',
  ], { stdio: ['ignore', 'pipe', 'pipe'] });

  // Wait for DevTools to be ready
  for (let i = 0; i < 30; i++) {
    await sleep(500);
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      if (res.ok) return;
    } catch { /* retry */ }
  }
  throw new Error('Chrome DevTools did not start');
}

async function connectCDP() {
  const res = await fetch(`http://127.0.0.1:${PORT}/json`);
  const targets = await res.json();
  const page = targets.find(t => t.type === 'page');
  if (!page) throw new Error('No page target found');

  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve } = pending.get(msg.id);
      pending.delete(msg.id);
      resolve(msg.result || msg);
    }
  };
}

async function evaluate(expression) {
  const result = await send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  return result?.result?.value;
}

async function run() {
  console.log('=== PC://CODE v0.1 — CDP Verification ===\n');

  // 1. Start HTTP server
  console.log('[1] Starting HTTP server on port ' + HTTP_PORT + '...');
  const server = await startHttpServer();
  console.log('    ✓ HTTP server ready');

  // 2. Start headless Chrome
  console.log('[2] Starting headless Chrome...');
  await startChrome();
  console.log('    ✓ Chrome ready');

  // 3. Connect CDP
  console.log('[3] Connecting CDP...');
  await connectCDP();
  console.log('    ✓ CDP connected');

  // 4. Navigate to page
  console.log('[4] Navigating to http://127.0.0.1:' + HTTP_PORT + '/webview/pc-code.html...');
  await send('Page.enable');
  await send('Page.navigate', { url: `http://127.0.0.1:${HTTP_PORT}/webview/pc-code.html` });
  await sleep(2000);
  console.log('    ✓ Page loaded');

  // 5. Verify page title
  const title = await evaluate('document.title');
  console.log('[5] Page title: ' + title);
  const titleOk = title === 'PC://CODE — Sovereign Agent';
  console.log('    ' + (titleOk ? '✓' : '✗') + ' Title check');

  // 6. Verify state machine renders
  const stateCount = await evaluate('document.querySelectorAll(".state-node").length');
  console.log('[6] State nodes rendered: ' + stateCount);
  const stateOk = stateCount === 10;
  console.log('    ' + (stateOk ? '✓' : '✗') + ' 10 states rendered');

  // 7. Verify state names
  const stateNames = await evaluate('Array.from(document.querySelectorAll(".state-node .name")).map(e => e.textContent)');
  const expected = ['IDLE','OBSERVE','PLAN','VALIDATE_PLAN','EXECUTE','DIAGNOSTICS','BUILD','TEST','REVIEW_DIFF','COMPLETE'];
  const namesOk = JSON.stringify(stateNames) === JSON.stringify(expected);
  console.log('[7] State names: ' + (namesOk ? '✓' : '✗') + ' ' + stateNames.join(', '));

  // 8. Click RUN and wait for completion
  console.log('[8] Running agent loop...');
  await evaluate('document.getElementById("runBtn").click()');
  await sleep(4000);

  // 9. Verify completion
  const status = await evaluate('document.getElementById("status").textContent');
  console.log('[9] Final status: ' + status);
  const statusOk = status === 'COMPLETE';
  console.log('    ' + (statusOk ? '✓' : '✗') + ' Loop completed');

  // 10. Verify receipts
  const receiptCount = await evaluate('document.querySelectorAll(".receipt").length');
  console.log('[10] Receipts generated: ' + receiptCount);
  const receiptOk = receiptCount === 10;
  console.log('    ' + (receiptOk ? '✓' : '✗') + ' 10 receipts');

  // 11. Verify chain status
  const chainText = await evaluate('document.getElementById("chainStatus").textContent');
  console.log('[11] Chain status: ' + chainText);
  const chainOk = chainText.includes('VALID');
  console.log('    ' + (chainOk ? '✓' : '✗') + ' Chain valid');

  // 12. Verify log entries
  const logCount = await evaluate('document.querySelectorAll(".log-entry").length');
  console.log('[12] Log entries: ' + logCount);
  const logOk = logCount >= 10;
  console.log('    ' + (logOk ? '✓' : '✗') + ' Log entries present');

  // 13. Verify effect classes shown
  const effects = await evaluate('Array.from(document.querySelectorAll(".state-node .effect")).map(e => e.textContent)');
  const hasLocal = effects.includes('LOCAL');
  const hasDurable = effects.includes('DURABLE');
  console.log('[13] Effect classes: LOCAL=' + hasLocal + ' DURABLE=' + hasDurable);
  console.log('    ' + ((hasLocal && hasDurable) ? '✓' : '✗') + ' Effect classes rendered');

  // 14. Verify no EXTERNAL effects
  const hasExternal = effects.includes('EXTERNAL');
  console.log('[14] No EXTERNAL effects: ' + (!hasExternal ? '✓' : '✗'));

  // 15. Verify hash chain integrity (check hashes are different)
  const hashes = await evaluate('Array.from(document.querySelectorAll(".receipt .hash")).map(e => e.textContent)');
  const uniqueHashes = new Set(hashes.map(h => h.replace('...', '')));
  const hashOk = uniqueHashes.size === hashes.length;
  console.log('[15] Unique receipt hashes: ' + hashOk + ' (' + uniqueHashes.size + '/' + hashes.length + ')');
  console.log('    ' + (hashOk ? '✓' : '✗') + ' All hashes unique');

  // Summary
  const allOk = titleOk && stateOk && namesOk && statusOk && receiptOk && chainOk && logOk && hasLocal && hasDurable && !hasExternal && hashOk;
  console.log('\n=== Verification ' + (allOk ? 'PASSED ✓' : 'FAILED ✗') + ' ===');
  console.log('Checks: ' + [titleOk, stateOk, namesOk, statusOk, receiptOk, chainOk, logOk, hasLocal && hasDurable, !hasExternal, hashOk].filter(Boolean).length + '/10 passed');

  // Cleanup
  ws.close();
  chrome.kill();
  server.close();

  process.exit(allOk ? 0 : 1);
}

run().catch(e => {
  console.error('Verification error:', e);
  if (chrome) chrome.kill();
  process.exit(1);
});
