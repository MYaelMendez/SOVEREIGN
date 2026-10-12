// Comprehensive CDP test for media-agent.html
// Tests: storyboard generation, render, VLC, WebMCP tools, receipts
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const URL_ = 'http://127.0.0.1:8123/media-agent.html';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9600 + Math.floor(Math.random() * 200);
const profile = mkdtempSync(path.join(tmpdir(), 'cdp-media-'));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--mute-audio',
  '--window-size=1280,720',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore' });

function cleanup(c) { try { chrome.kill(); } catch {} try { rmSync(profile, { recursive: true, force: true }); } catch {} process.exit(c); }

async function waitDevtools() {
  for (let i = 0; i < 120; i++) { try { const r = await fetch(`http://127.0.0.1:${PORT}/json/version`); if (r.ok) return; } catch {} await sleep(150); }
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

const TEST_EXPR = `(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const results = {};

  // Wait for app to be ready
  while (!window.__MEDIA_AGENT__) await sleep(200);
  results.ready = true;
  results.config = {
    scenes: window.__MEDIA_AGENT__.scenes,
    sceneDuration: window.__MEDIA_AGENT__.sceneDuration,
    totalDuration: window.__MEDIA_AGENT__.totalDuration,
    fps: window.__MEDIA_AGENT__.fps,
    totalFrames: window.__MEDIA_AGENT__.totalFrames,
    nodes: window.__MEDIA_AGENT__.nodes,
    edges: window.__MEDIA_AGENT__.edges,
  };

  // Test 1: Storyboard generation
  document.getElementById('concept-input').value = '21s video of the agentic electronic engineering constellation';
  window.app.generateStoryboard();
  await sleep(500);
  results.storyboard = {
    scenes: window.__MEDIA_AGENT__.state.storyboard.length,
    firstScene: window.__MEDIA_AGENT__.state.storyboard[0]?.name,
    lastScene: window.__MEDIA_AGENT__.state.storyboard[11]?.name,
  };

  // Test 2: Viewport initialized
  results.viewport = {
    hasCanvas: !!document.querySelector('canvas'),
    hasNodeGroup: !!window.__MEDIA_AGENT__.state.nodeGroup,
    hasRenderer: !!window.__MEDIA_AGENT__.state.renderer,
  };

  // Test 3: Render pipeline
  window.app.startRender();
  await sleep(1000);
  results.render = {
    isRendering: window.__MEDIA_AGENT__.state.isRendering,
    frame: window.__MEDIA_AGENT__.state.renderFrame,
  };
  window.app.stopRender();

  // Test 4: VLC verification
  await window.app.testVLC();
  results.vlc = {
    tested: window.__MEDIA_AGENT__.state.vlcTested,
    statusText: document.getElementById('vlc-status').textContent,
  };

  // Test 5: WebMCP tools
  const toolResults = {};
  for (const tool of ['scene_create', 'video_render', 'playback_control', 'receipt_verify']) {
    await window.app.webmcpCall(tool);
    await sleep(200);
  }
  results.webmcp = {
    tools: window.__MEDIA_AGENT__.webmcpTools,
    publishStatus: document.getElementById('publish-status').textContent,
  };

  // Test 6: Receipts
  results.receipts = {
    count: window.__MEDIA_AGENT__.state.receipts.length,
    first: window.__MEDIA_AGENT__.state.receipts[0] ? {
      asset: window.__MEDIA_AGENT__.state.receipts[0].asset,
      hashLen: window.__MEDIA_AGENT__.state.receipts[0].hash.length,
      hashPrefix: window.__MEDIA_AGENT__.state.receipts[0].hash.substr(0, 16),
    } : null,
  };

  // Test 7: Pipeline stages
  results.stages = {
    input: document.getElementById('stage-input').className,
    storyboard: document.getElementById('stage-storyboard').className,
    render: document.getElementById('stage-render').className,
    verify: document.getElementById('stage-verify').className,
    publish: document.getElementById('stage-publish').className,
  };

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
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = (e) => rej(new Error('ws error')); });
    ws.onmessage = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); return; }
      if (m.method === 'Runtime.consoleAPICalled') logs.push('[' + m.params.type + '] ' + (m.params.args || []).map(a => a.value ?? a.description ?? a.type).join(' '));
      if (m.method === 'Runtime.exceptionThrown') logs.push('[exception] ' + (m.params.exceptionDetails?.exception?.description || m.params.exceptionDetails?.text || '').slice(0, 500));
    };
    await send('Runtime.enable');
    await send('Page.enable');
    await sleep(3000);

    const r = await send('Runtime.evaluate', { expression: TEST_EXPR, returnByValue: true, awaitPromise: true, timeout: 30000 });
    if (r.exceptionDetails) {
      console.log('EVAL EXCEPTION:', JSON.stringify(r.exceptionDetails).slice(0, 1000));
    }
    console.log('=== MEDIA AGENT TEST RESULTS ===');
    console.log(typeof r.result?.value === 'string' ? r.result.value : JSON.stringify(r.result?.value, null, 1));
    if (logs.length) {
      console.log('=== CONSOLE (' + logs.length + ') ===');
      console.log(logs.slice(-30).join('\n'));
    }
    cleanup(0);
  } catch (e) {
    console.log('DRIVER ERROR: ' + (e && e.stack || e));
    cleanup(3);
  }
})();
