// Minimal CDP driver: launch headless Chrome, open a URL, poll window.__RESULT, print it.
// Usage: node _cdp.mjs <url> [timeoutMs] [resultExpr]
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const URL_ = process.argv[2];
const TIMEOUT = parseInt(process.argv[3] || '25000', 10);
const EXPR = process.argv[4] || 'window.__RESULT';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9333 + Math.floor(Math.random() * 400);
const profile = mkdtempSync(path.join(tmpdir(), 'cdp-'));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--mute-audio',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore' });

function cleanup(code) { try { chrome.kill(); } catch {} try { rmSync(profile, { recursive: true, force: true }); } catch {} process.exit(code); }

async function waitDevtools() {
  for (let i = 0; i < 100; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      if (r.ok) return;
    } catch {}
    await sleep(150);
  }
  throw new Error('devtools not up');
}

async function newTarget(url) {
  for (let i = 0; i < 40; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
      if (r.ok) { const j = await r.json(); if (j.webSocketDebuggerUrl) return j; }
    } catch {}
    await sleep(200);
  }
  throw new Error('could not create target');
}

(async () => {
  try {
    await waitDevtools();
    const t = await newTarget(URL_);
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    let id = 0; const pending = new Map();
    const send = (method, params = {}) => new Promise((res, rej) => {
      const mid = ++id; pending.set(mid, { res, rej });
      ws.send(JSON.stringify({ id: mid, method, params }));
    });
    const consoleLogs = [];
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = (e) => rej(new Error('ws error')); });
    ws.onmessage = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); return; }
      if (m.method === 'Runtime.consoleAPICalled') {
        const args = (m.params.args || []).map((a) => a.value ?? a.description ?? a.type).join(' ');
        consoleLogs.push(`[${m.params.type}] ${args}`);
      }
      if (m.method === 'Runtime.exceptionThrown') {
        const d = m.params.exceptionDetails || {};
        consoleLogs.push(`[exception] ${d.exception?.description || d.text || JSON.stringify(d).slice(0, 300)}`);
      }
    };
    await send('Runtime.enable');
    await send('Page.enable');

    let result = null; let lastErr = null;
    const t0 = Date.now();
    while (Date.now() - t0 < TIMEOUT) {
      await sleep(400);
      try {
        const r = await send('Runtime.evaluate', { expression: EXPR, returnByValue: true, awaitPromise: false });
        const v = r && r.result ? r.result.value : undefined;
        if (v !== undefined && v !== null) { result = v; break; }
        if (r && r.exceptionDetails) lastErr = r.exceptionDetails.text;
      } catch (e) { lastErr = e.message; }
    }
    console.log('=== RESULT ===');
    console.log(typeof result === 'string' ? result : JSON.stringify(result, null, 1));
    console.log('=== CONSOLE (' + consoleLogs.length + ') ===');
    console.log(consoleLogs.slice(-40).join('\n'));
    if (lastErr) console.log('=== LAST EVAL ERR === ' + lastErr);
    cleanup(result != null ? 0 : 2);
  } catch (e) {
    console.log('DRIVER ERROR: ' + (e && e.stack || e));
    cleanup(3);
  }
})();
