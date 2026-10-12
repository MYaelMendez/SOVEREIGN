// Capture a screenshot of the tower-sync page (prove it actually draws).
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const URL_ = process.argv[2] || 'http://127.0.0.1:8137/index.html';
const OUT = process.argv[3] || 'C:/æ/tower-sync/_shot.png';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9800 + Math.floor(Math.random() * 400);
const profile = mkdtempSync(path.join(tmpdir(), 'cdp-'));
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new','--disable-gpu','--enable-unsafe-swiftshader','--use-angle=swiftshader',
  '--no-first-run','--no-default-browser-check','--disable-extensions','--mute-audio','--window-size=1280,800',
  `--remote-debugging-port=${PORT}`,`--user-data-dir=${profile}`,'about:blank'], { stdio:'ignore' });
function cleanup(c){try{chrome.kill()}catch{}try{rmSync(profile,{recursive:true,force:true})}catch{}process.exit(c)}
async function waitDev(){for(let i=0;i<120;i++){try{const r=await fetch(`http://127.0.0.1:${PORT}/json/version`);if(r.ok)return}catch{}await sleep(150)}throw new Error('no devtools')}
async function newTarget(u){for(let i=0;i<40;i++){try{const r=await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(u)}`,{method:'PUT'});if(r.ok){const j=await r.json();if(j.webSocketDebuggerUrl)return j}}catch{}await sleep(200)}throw new Error('no target')}
(async()=>{try{
  await waitDev(); const t=await newTarget(URL_);
  const ws=new WebSocket(t.webSocketDebuggerUrl); let id=0; const pend=new Map();
  const send=(m,p={})=>new Promise(res=>{const i=++id;pend.set(i,res);ws.send(JSON.stringify({id:i,method:m,params:p}))});
  await new Promise(r=>ws.addEventListener('open',r));
  ws.addEventListener('message',ev=>{const m=JSON.parse(ev.data);if(m.id&&pend.has(m.id)){pend.get(m.id)(m.result);pend.delete(m.id)}});
  await send('Page.enable');
  await send('Page.navigate',{url:URL_});
  await sleep(9000);
  const shot=await send('Page.captureScreenshot',{format:'png'});
  writeFileSync(OUT, Buffer.from(shot.data,'base64'));
  console.log('SHOT: '+OUT);
  cleanup(0);
}catch(e){console.log('ERR: '+e.message);cleanup(1)}})();
