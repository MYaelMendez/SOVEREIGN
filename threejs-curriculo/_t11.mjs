// Deterministic effect verification for Fase 11.
// Launches headless Chrome, freezes the render loop, then A/B-renders each
// effect on/off and reports mean-absolute pixel-grid differences.
// Usage: node _t11.mjs <url>
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const URL_ = process.argv[2] || 'http://127.0.0.1:8011/fase11-efectos-avanzados.html';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9700 + Math.floor(Math.random() * 200);
const profile = mkdtempSync(path.join(tmpdir(), 'cdp11-'));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const TEST = `(async () => {
  const A = window.__fase11;
  if (!A) return JSON.stringify({ ok:false, error:'__fase11 missing' });
  A.freeze();
  await new Promise(r => setTimeout(r, 60));

  const ids = ['ssr','dof','motion','vol','grade','fxaa'];
  const setAll = (on) => ids.forEach(id => A.toggle(id, on));
  const grid = () => Array.from(A.grid());
  const diff = (a,b) => { let s=0; for (let i=0;i<a.length;i++) s+=Math.abs(a[i]-b[i]); return +(s/a.length).toFixed(3); };

  // baseline: only RenderPass + OutputPass
  setAll(false);
  const base = (() => { A.renderNow(); return grid(); })();

  const R = {};
  // each effect isolated
  for (const id of ids) {
    setAll(false); A.toggle(id, true);
    A.renderNow();
    R[id] = diff(base, grid());
  }

  // DOF focus sweep: near focus vs far focus must differ
  setAll(false); A.toggle('dof', true);
  A.focusAt(2.5);  A.renderNow(); const dofNear = grid();
  A.focusAt(35.0); A.renderNow(); const dofFar  = grid();
  R.dof_focus_sweep = diff(dofNear, dofFar);

  // Motion blur needs inter-frame camera motion: render at P0, move, render at P1
  setAll(false);
  A.camera.position.x = 7.5; A.renderNow();
  A.camera.position.x = 8.6;                       // move camera
  A.toggle('motion', true);  A.renderNow(); const mbOn  = grid();
  A.toggle('motion', false); A.renderNow(); const mbOff = grid();
  R.motion_velocity = diff(mbOn, mbOff);

  // Tone mapping: ACES vs Reinhard vs Filmic(Cineon) vs AgX vs None
  setAll(false);
  const tm = {};
  for (const [n,v] of [['aces',4],['reinhard',3],['filmic',2],['agx',6],['none',0]]) {
    A.setToneMapping(v); A.renderNow(); tm[n] = grid();
  }
  R.tm_aces_vs_reinhard = diff(tm.aces, tm.reinhard);
  R.tm_aces_vs_filmic   = diff(tm.aces, tm.filmic);
  R.tm_aces_vs_agx      = diff(tm.aces, tm.agx);
  R.tm_aces_vs_none     = diff(tm.aces, tm.none);
  A.setToneMapping(4);

  // LUT grading: neutral vs noir vs cyberpunk
  setAll(false); A.toggle('grade', true);
  A.setLUT('Neutral (identidad)');        A.renderNow(); const lutN = grid();
  A.setLUT('Noir (B/N alto contraste)');  A.renderNow(); const lutB = grid();
  A.setLUT('Cyberpunk (magenta/cian)');   A.renderNow(); const lutC = grid();
  R.lut_neutral_vs_noir  = diff(lutN, lutB);
  R.lut_neutral_vs_cyber = diff(lutN, lutC);
  A.setLUT('Teal & Orange');

  // restore
  setAll(true);
  A.resume();
  return JSON.stringify({ ok: true, diffs: R, errors: window.__ERRORS });
})()`;

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--mute-audio',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore' });

function cleanup(code) { try { chrome.kill(); } catch {} try { rmSync(profile, { recursive:true, force:true }); } catch {} process.exit(code); }

(async () => {
  try {
    for (let i = 0; i < 100; i++) {
      try { const r = await fetch(`http://127.0.0.1:${PORT}/json/version`); if (r.ok) break; } catch {}
      await sleep(150);
    }
    const tr = await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(URL_)}`, { method:'PUT' });
    const t = await tr.json();
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    let id = 0; const pending = new Map();
    const send = (method, params = {}) => new Promise((res, rej) => {
      const mid = ++id; pending.set(mid, { res, rej });
      ws.send(JSON.stringify({ id: mid, method, params }));
    });
    const logs = [];
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws error')); });
    ws.onmessage = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); return; }
      if (m.method === 'Runtime.consoleAPICalled') logs.push('[' + m.params.type + '] ' + (m.params.args||[]).map(a=>a.value??a.description??a.type).join(' '));
      if (m.method === 'Runtime.exceptionThrown') logs.push('[exception] ' + (m.params.exceptionDetails?.exception?.description || m.params.exceptionDetails?.text));
    };
    await send('Runtime.enable');
    await send('Page.enable');

    // wait for the module to finish booting
    let ready = false;
    for (let i = 0; i < 60; i++) {
      await sleep(300);
      const r = await send('Runtime.evaluate', { expression: '!!window.__fase11', returnByValue: true });
      if (r.result && r.result.value === true) { ready = true; break; }
    }
    if (!ready) { console.log('BOOT FAILED'); console.log(logs.join('\n')); cleanup(2); }

    await sleep(900); // let a few frames render
    const r = await send('Runtime.evaluate', { expression: TEST, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) { console.log('TEST EXCEPTION: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text)); }
    const val = r.result && r.result.value;
    console.log('=== TEST ===');
    console.log(typeof val === 'string' ? val : JSON.stringify(val, null, 1));
    console.log('=== CONSOLE (' + logs.length + ') ===');
    console.log(logs.slice(-30).join('\n'));
    cleanup(0);
  } catch (e) {
    console.log('DRIVER ERROR: ' + (e && e.stack || e));
    cleanup(3);
  }
})();
