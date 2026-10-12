// CDP verification for storyboard.html
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const URL_ = process.argv[2] || 'http://127.0.0.1:8123/storyboard.html';
const TIMEOUT = parseInt(process.argv[3] || '30000', 10);
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9500 + Math.floor(Math.random() * 300);
const profile = mkdtempSync(path.join(tmpdir(), 'cdp-sb-'));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--mute-audio',
  '--window-size=1280,720',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore' });

function cleanup(c) { try { chrome.kill(); } catch {} try { rmSync(profile, { recursive: true, force: true }); } catch {} process.exit(c); }

async function waitDevtools() {
  for (let i = 0; i < 120; i++) {
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
  throw new Error('no target');
}

const EXPR = `(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  while (!window.__STORYBOARD__) await sleep(100);
  const SB = window.__STORYBOARD__;
  const app = window.app;

  const results = {};

  // 1. Basic info
  results.ready = SB.ready;
  results.version = SB.version;
  results.scenes = SB.scenes;
  results.sceneDuration = SB.sceneDuration;
  results.totalDuration = SB.totalDuration;
  results.fps = SB.fps;
  results.totalFrames = SB.totalFrames;
  results.nodes = SB.nodes;
  results.edges = SB.edges;
  results.webmcpTools = SB.webmcpTools;

  // 2. Scene definitions
  results.sceneDefs = SB.sceneDefs.map(s => ({
    id: s.id, name: s.name,
    cameraPos: s.camera.pos, cameraTarget: s.camera.target, fov: s.camera.fov,
    nodes: s.nodes.length, transition: s.transition, duration: s.duration,
  }));

  // 3. Generate storyboard
  app.generate();
  results.storyboardGenerated = app.state.storyboard.length;
  results.concept = app.state.concept;

  // 4. Check scene details
  results.sceneDetails = app.state.storyboard.map(s => ({
    id: s.id, name: s.name,
    nodes: s.nodes.length, transition: s.transition,
    startTime: s.startTime, endTime: s.endTime,
  }));

  // 5. Test WebMCP tools
  const createResult = await app.webmcpCreate();
  results.webmcpCreate = createResult ? createResult.status : 'failed';

  const exportResult = await app.webmcpExport();
  results.webmcpExport = exportResult ? exportResult.status : 'failed';
  results.receiptGenerated = exportResult && exportResult.receipt ? exportResult.receipt.hash.substr(0, 16) : 'none';

  const previewResult = await app.webmcpPreview();
  results.webmcpPreview = previewResult ? previewResult.status : 'failed';

  // 6. Test export
  const exported = app.exportJSON();
  results.exportedSize = exported ? exported.length : 0;

  // 7. Test import (round-trip)
  if (exported) {
    app.doImport(exported);
    results.importRoundTrip = app.state.storyboard.length;
  }

  // 8. Test playback controls
  app.togglePlay();
  results.isPlaying = app.state.isPlaying;
  app.seek(5.0);
  results.seekTime = app.state.currentTime;
  results.seekScene = app.state.currentScene;
  app.togglePlay();

  // 9. Three.js scene check
  results.hasScene = !!app.state.scene;
  results.hasCamera = !!app.state.camera;
  results.hasRenderer = !!app.state.renderer;
  results.nodeMapSize = Object.keys(app.state.nodeMap).length;

  // 10. Receipts
  results.receiptsCount = app.state.receipts.length;

  return JSON.stringify(results, null, 1);
})()`;

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
    const logs = [];
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws')); });
    ws.onmessage = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); return; }
      if (m.method === 'Runtime.consoleAPICalled') logs.push('[' + m.params.type + '] ' + (m.params.args||[]).map(a=>a.value??a.description).join(' '));
      if (m.method === 'Runtime.exceptionThrown') logs.push('[exc] ' + (m.params.exceptionDetails?.exception?.description || '').slice(0,500));
    };
    await send('Runtime.enable'); await send('Page.enable');
    await sleep(3000);
    const r = await send('Runtime.evaluate', { expression: EXPR, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) console.log('EVAL EXC: ' + JSON.stringify(r.exceptionDetails).slice(0, 900));
    console.log('=== VERIFY ===');
    console.log(typeof r.result?.value === 'string' ? r.result.value : JSON.stringify(r.result?.value, null, 1));
    if (logs.length) { console.log('=== CONSOLE ==='); console.log(logs.slice(-25).join('\\n')); }
    cleanup(0);
  } catch (e) { console.log('DRIVER ERROR: ' + (e && e.stack || e)); cleanup(3); }
})();
