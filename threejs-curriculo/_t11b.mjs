// Refined verification: DOF focus in-range, motion blur across live frames,
// SSR scaling, preview modes, all-on sanity. Usage: node _t11b.mjs <url>
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const URL_ = process.argv[2] || 'http://127.0.0.1:8011/fase11-efectos-avanzados.html';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9900 + Math.floor(Math.random() * 90);
const profile = mkdtempSync(path.join(tmpdir(), 'cdp11b-'));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const TEST = `(async () => {
  const A = window.__fase11;
  A.freeze();
  await new Promise(r => setTimeout(r, 60));
  const ids = ['ssr','dof','motion','vol','grade','fxaa'];
  const setAll = (on) => ids.forEach(id => A.toggle(id, on));
  const grid = () => Array.from(A.grid());
  const diff = (a,b) => { let s=0; for (let i=0;i<a.length;i++) s+=Math.abs(a[i]-b[i]); return +(s/a.length).toFixed(3); };
  const R = {};

  // ── DOF: focus IN-RANGE. focus 10 ≈ knot plane vs focus 2 (all blurred)
  setAll(false); A.toggle('dof', true);
  A.focusAt(10.0); A.renderNow(); const f10 = grid();
  A.focusAt(2.0);  A.renderNow(); const f2  = grid();
  A.focusAt(20.0); A.renderNow(); const f20 = grid();
  R.dof_focus10_vs_focus2  = diff(f10, f2);    // in-focus vs fully blurred
  R.dof_focus10_vs_focus20 = diff(f10, f20);   // in-focus vs far-blurred
  R.dof_focus2_vs_focus20  = diff(f2, f20);
  A.focusAt(9.0);

  // ── Motion blur across LIVE frames (camera moves between two real renders)
  setAll(false);
  A.camera.position.set(7.5, 4.6, 10.5); A.renderNow();   // establishes prev VP
  A.camera.position.set(8.8, 4.6, 10.5); A.renderNow();   // frame N (camera jumped)
  const mbOn1 = grid();
  A.toggle('motion', true);
  A.camera.position.set(7.5, 4.6, 10.5); A.renderNow();
  A.camera.position.set(8.8, 4.6, 10.5); A.renderNow();
  const mbOn2 = grid();
  // same jump, motion OFF
  A.toggle('motion', false);
  A.camera.position.set(7.5, 4.6, 10.5); A.renderNow();
  A.camera.position.set(8.8, 4.6, 10.5); A.renderNow();
  const mbOff = grid();
  R.motion_live_on_vs_off = diff(mbOn2, mbOff);
  // strength scaling
  A.toggle('motion', true);
  A.passes.motionPass.uniforms.strength.value = 0.0;
  A.camera.position.set(7.5, 4.6, 10.5); A.renderNow(); A.camera.position.set(8.8,4.6,10.5); A.renderNow();
  const mbS0 = grid();
  A.passes.motionPass.uniforms.strength.value = 2.0;
  A.camera.position.set(7.5, 4.6, 10.5); A.renderNow(); A.camera.position.set(8.8,4.6,10.5); A.renderNow();
  const mbS2 = grid();
  R.motion_strength0_vs_2 = diff(mbS0, mbS2);
  A.passes.motionPass.uniforms.strength.value = 1.0;
  A.camera.position.set(7.5, 4.6, 10.5);

  // ── SSR intensity scaling (proves it is not noise)
  setAll(false); A.toggle('ssr', true);
  A.passes.ssrPass.uniforms.intensity.value = 0.0; A.renderNow(); const s0 = grid();
  A.passes.ssrPass.uniforms.intensity.value = 1.8; A.renderNow(); const s18 = grid();
  R.ssr_intensity0_vs_1_8 = diff(s0, s18);
  A.passes.ssrPass.uniforms.intensity.value = 0.85;

  // ── Volumetric density scaling
  setAll(false); A.toggle('vol', true);
  A.passes.volPass.uniforms.density.value = 0.0; A.renderNow(); const v0 = grid();
  A.passes.volPass.uniforms.density.value = 2.5; A.renderNow(); const v25 = grid();
  R.vol_density0_vs_2_5 = diff(v0, v25);
  A.passes.volPass.uniforms.density.value = 0.9;

  // ── all-on sanity: no errors, still renders
  setAll(true); A.renderNow();
  const allOn = grid();
  let mean = 0; for (let i=0;i<allOn.length;i++) mean += allOn[i];
  R.all_on_mean = +(mean/allOn.length).toFixed(2);
  R.errors = window.__ERRORS.length;

  A.resume();
  return JSON.stringify({ ok:true, diffs:R });
})()`;

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--mute-audio',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore' });
function cleanup(c){ try{chrome.kill();}catch{} try{rmSync(profile,{recursive:true,force:true});}catch{} process.exit(c); }

(async () => {
  try {
    for (let i=0;i<100;i++){ try{ const r=await fetch(`http://127.0.0.1:${PORT}/json/version`); if(r.ok) break; }catch{} await sleep(150); }
    const t = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(URL_)}`,{method:'PUT'})).json();
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    let id=0; const pending=new Map();
    const send=(m,p={})=>new Promise((res,rej)=>{const i=++id;pending.set(i,{res,rej});ws.send(JSON.stringify({id:i,method:m,params:p}));});
    const logs=[];
    await new Promise((res,rej)=>{ws.onopen=res;ws.onerror=()=>rej(new Error('ws'));});
    ws.onmessage=(ev)=>{let m;try{m=JSON.parse(ev.data);}catch{return;}
      if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result);return;}
      if(m.method==='Runtime.exceptionThrown')logs.push('[exc] '+(m.params.exceptionDetails?.exception?.description||m.params.exceptionDetails?.text));};
    await send('Runtime.enable'); await send('Page.enable');
    let ready=false;
    for(let i=0;i<60;i++){ await sleep(300); const r=await send('Runtime.evaluate',{expression:'!!window.__fase11',returnByValue:true}); if(r.result&&r.result.value===true){ready=true;break;} }
    if(!ready){ console.log('BOOT FAILED'); console.log(logs.join('\n')); cleanup(2); }
    await sleep(900);
    const r = await send('Runtime.evaluate',{expression:TEST,returnByValue:true,awaitPromise:true});
    if(r.exceptionDetails) console.log('TEST EXCEPTION: '+(r.exceptionDetails.exception?.description||r.exceptionDetails.text));
    console.log('=== TEST B ===');
    console.log(typeof r.result?.value==='string'?r.result.value:JSON.stringify(r.result?.value,null,1));
    if(logs.length) console.log('=== LOGS ===\n'+logs.slice(-20).join('\n'));
    cleanup(0);
  } catch(e){ console.log('DRIVER ERROR: '+(e&&e.stack||e)); cleanup(3); }
})();
