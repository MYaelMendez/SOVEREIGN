// Verificación determinista Fase 11: congela la animación y compara grillas de píxeles.
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const URL_ = process.argv[2];
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9800 + Math.floor(Math.random() * 150);
const profile = mkdtempSync(path.join(tmpdir(), 'cdpv2-'));
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
    try { const r = await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
      if (r.ok) { const j = await r.json(); if (j.webSocketDebuggerUrl) return j; } } catch {}
    await sleep(200);
  }
  throw new Error('no target');
}

const EXPR = `(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  while (!window.__fase11) await sleep(100);
  const F = window.__fase11;
  F.freeze();                       // determinista: renderNow() pinta un frame exacto
  const GW = 48, GH = 27;

  function stats() {
    const g = F.grid();             // Uint8Array GW*GH*3 del framebuffer recién pintado
    let n = 0, sr = 0, sg = 0, sb = 0, l = 0, l2 = 0;
    for (let i = 0; i < g.length; i += 3) {
      const R = g[i], G = g[i+1], B = g[i+2];
      const L = 0.2126*R + 0.7152*G + 0.0722*B;
      sr += R; sg += G; sb += B; l += L; l2 += L*L; n++;
    }
    const m = l/n;
    return { grid: Array.from(g), r:+(sr/n).toFixed(2), g:+(sg/n).toFixed(2), b:+(sb/n).toFixed(2),
             lum:+m.toFixed(2), var:+(l2/n-m*m).toFixed(1) };
  }
  function mad(a, b) {             // mean absolute difference sobre la grilla
    let s = 0; for (let i = 0; i < a.length; i++) s += Math.abs(a[i] - b[i]);
    return +(s / a.length).toFixed(2);
  }

  const out = {}, grids = {};
  function snap(label, setup) {
    if (setup) setup();
    F.renderNow();
    const st = stats();
    grids[label] = st.grid; delete st.grid;
    out[label] = st;
  }

  const allOff = () => ['ssr','dof','motion','vol','grade','fxaa'].forEach(id => F.toggle(id, false));
  const lutNames = Object.keys(F.luts);

  // ── baseline ──
  allOff(); F.setToneMapping(4); F.setExposure(1);
  snap('baseline');

  // ── DOF ──
  F.toggle('dof', true);
  snap('dof_near', () => F.focusAt(2.0));
  snap('dof_mid',  () => F.focusAt(9.0));
  snap('dof_far',  () => F.focusAt(40.0));
  F.toggle('dof', false);

  // ── SSR ──
  F.toggle('ssr', true);
  snap('ssr_on');
  snap('ssr_strong', () => F.setControl('ssr', 'intensity', 2.0));
  F.setControl('ssr', 'intensity', 0.8);
  F.toggle('ssr', false);

  // ── Volumétricas ──
  F.toggle('vol', true);
  snap('vol_on');
  snap('vol_strong', () => { F.setControl('vol', 'lightIntensity', 3.0); F.setControl('vol', 'density', 2.5); });
  F.setControl('vol', 'lightIntensity', 1.0); F.setControl('vol', 'density', 0.9);
  F.toggle('vol', false);

  // ── Tone mapping ──
  snap('tone_none',     () => F.setToneMapping(0));
  snap('tone_aces',     () => F.setToneMapping(4));
  snap('tone_reinhard', () => F.setToneMapping(3));
  snap('tone_filmic',   () => F.setToneMapping(2));
  snap('tone_agx',      () => F.setToneMapping(5));
  snap('tone_exposure2',() => { F.setToneMapping(4); F.setExposure(2.0); });
  F.setExposure(1);

  // ── LUTs ──
  F.toggle('grade', true);
  snap('lut_neutral', () => F.setLUT(lutNames[0]));
  snap('lut_teal',    () => F.setLUT(lutNames[1]));
  snap('lut_warm',    () => F.setLUT(lutNames[2]));
  snap('lut_noir',    () => F.setLUT(lutNames[4]));
  snap('lut_cyber',   () => F.setLUT(lutNames[5]));
  F.toggle('grade', false);

  // ── FXAA ──
  F.toggle('fxaa', true);
  snap('fxaa_on');
  F.toggle('fxaa', false);

  // ── Motion blur: con la animación congelada hay que mover la cámara a mano ──
  F.controls.autoRotate = true; F.controls.autoRotateSpeed = 12;
  F.toggle('motion', false);
  F.renderNow();                       // frame 1 (sin blur)
  const noBlur = stats();
  F.toggle('motion', true);
  F.renderNow();                       // frame 2 con velocity de la rotación
  F.renderNow();
  const withBlur = stats();
  out['motion_cam_moved_off'] = { r:noBlur.r, g:noBlur.g, b:noBlur.b, lum:noBlur.lum, var:noBlur.var };
  out['motion_cam_moved_on']  = { r:withBlur.r, g:withBlur.g, b:withBlur.b, lum:withBlur.lum, var:withBlur.var };
  grids['motion_cam_moved_off'] = noBlur.grid;
  grids['motion_cam_moved_on']  = withBlur.grid;
  F.controls.autoRotate = false;
  F.toggle('motion', false);

  // ── diferencias contra baseline ──
  const diffs = {};
  for (const k in grids) diffs[k] = mad(grids[k], grids.baseline);

  return JSON.stringify({ errors: window.__ERRORS, stats: out, madVsBaseline: diffs }, null, 1);
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
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws')); });
    const logs = [];
    ws.onmessage = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id);
        m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); return; }
      if (m.method === 'Runtime.consoleAPICalled') logs.push('[' + m.params.type + '] ' + (m.params.args||[]).map(a=>a.value??a.description).join(' '));
      if (m.method === 'Runtime.exceptionThrown') logs.push('[exc] ' + (m.params.exceptionDetails?.exception?.description || '').slice(0,300));
    };
    await send('Runtime.enable'); await send('Page.enable');
    await sleep(3000);
    const r = await send('Runtime.evaluate', { expression: EXPR, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) console.log('EVAL EXC: ' + JSON.stringify(r.exceptionDetails).slice(0, 900));
    console.log('=== VERIFY ===');
    console.log(typeof r.result?.value === 'string' ? r.result.value : JSON.stringify(r.result?.value, null, 1));
    if (logs.length) { console.log('=== CONSOLE ==='); console.log(logs.slice(-25).join('\n')); }
    cleanup(0);
  } catch (e) { console.log('DRIVER ERROR: ' + (e && e.stack || e)); cleanup(3); }
})();
