// Headless render check for tower-sync: load the page, wait, report JS errors + __TOWER__ state.
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const URL_ = process.argv[2] || 'http://127.0.0.1:8137/index.html';
const TIMEOUT = parseInt(process.argv[3] || '20000', 10);
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9400 + Math.floor(Math.random() * 400);
const profile = mkdtempSync(path.join(tmpdir(), 'cdp-'));
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--mute-audio',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore' });

function cleanup(code) { try { chrome.kill(); } catch {} try { rmSync(profile, {recursive:true, force:true}); } catch {} process.exit(code); }

async function waitDevtools() {
  for (let i = 0; i < 120; i++) {
    try { const r = await fetch(`http://127.0.0.1:${PORT}/json/version`); if (r.ok) return; } catch {}
    await sleep(150);
  }
  throw new Error('devtools not up');
}
async function newTarget(url) {
  for (let i = 0; i < 40; i++) {
    try { const r = await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(url)}`, {method:'PUT'});
      if (r.ok) { const j = await r.json(); if (j.webSocketDebuggerUrl) return j; } } catch {}
    await sleep(200);
  }
  throw new Error('no target');
}

const errors = [];
(async () => {
  try {
    await waitDevtools();
    const t = await newTarget(URL_);
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    let id = 0; const pend = new Map();
    const send = (method, params={}) => new Promise(res => { const i = ++id; pend.set(i, res); ws.send(JSON.stringify({id:i, method, params})); });
    await new Promise(r => ws.addEventListener('open', r));
    ws.addEventListener('message', ev => {
      const m = JSON.parse(ev.data);
      if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); }
      if (m.method === 'Runtime.exceptionThrown') {
        const d = m.params.exceptionDetails;
        errors.push(d.exception?.description || d.text || 'exception');
      }
      if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
        errors.push('console.error: ' + m.params.args.map(a => a.value || a.description).join(' '));
      }
    });
    await send('Runtime.enable');
    await send('Page.enable');
    await send('Page.navigate', { url: URL_ });
    await sleep(TIMEOUT);
    const r = await send('Runtime.evaluate', {
      expression: `JSON.stringify({ tower: window.__TOWER__ ? {ready:window.__TOWER__.ready, nodes:window.__TOWER__.nodes, rings:window.__TOWER__.rings, version:window.__TOWER__.version} : null,
        canvas: !!document.querySelector('canvas'),
        canvasW: (document.querySelector('canvas')||{}).width,
        status: (document.getElementById('status')||{}).textContent,
        ringItems: document.querySelectorAll('.ring-item').length,
        gateDisplay: (document.getElementById('gate')||{}).style.display,
        webgl: (()=>{try{const c=document.createElement('canvas');return !!(c.getContext('webgl2')||c.getContext('webgl'));}catch(e){return false;}})()
      })`, returnByValue: true });
    console.log('STATE: ' + r.result.value);
    console.log('ERRORS(' + errors.length + '): ' + JSON.stringify(errors.slice(0, 10)));
    cleanup(errors.length ? 2 : 0);
  } catch (e) {
    console.log('DRIVER ERROR: ' + e.message);
    cleanup(3);
  }
})();
