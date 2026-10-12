#!/usr/bin/env node
// Render internetofagents.html with polling for the __renderFrame hook
import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';

const NODE_EXE = 'C:/Users/yaelm/AppData/Local/hermes/tools/node-26.7.0-win32-x64/node.exe';
const RENDER_MJS = 'C:/æ/threejs-curriculo/render.mjs';

// Read the URL and args
const args = process.argv.slice(2);
const urlIdx = args.indexOf('--url=');
const url = urlIdx >= 0 ? args[urlIdx].split('=')[1] : 'http://127.0.0.1:8124/internetofagents.html';
const outIdx = args.indexOf('--out=');
const out = outIdx >= 0 ? args[outIdx].split('=')[1] : 'C:/æ/github-pages/internetofagents.mp4';
const framesIdx = args.indexOf('--frames=');
const frames = framesIdx >= 0 ? parseInt(args[framesIdx].split('=')[1]) : 450;
const fpsIdx = args.indexOf('--fps=');
const fps = fpsIdx >= 0 ? parseInt(args[fpsIdx].split('=')[1]) : 30;
const wIdx = args.indexOf('--w=');
const w = wIdx >= 0 ? parseInt(args[wIdx].split('=')[1]) : 1280;
const hIdx = args.indexOf('--h=');
const h = hIdx >= 0 ? parseInt(args[hIdx].split('=')[1]) : 720;
const encIdx = args.indexOf('--encoder=');
const enc = encIdx >= 0 ? args[encIdx].split('=')[1] : 'nvenc';

console.log(`[render-io] url=${url}`);
console.log(`[render-io] out=${out} frames=${frames} fps=${fps} ${w}x${h} encoder=${enc}`);

// Read render.mjs
let src = readFileSync(RENDER_MJS, 'utf8');

// Patch to poll for the hook
const pollingCode = `
// ── Poll for the hook ──
let hasHook = false;
let pollTries = 0;
const POLL_MAX = 30;
while (pollTries < POLL_MAX && !hasHook) {
  const probe = await send('Runtime.evaluate', {
    expression: 'typeof window.__renderFrame === "function"',
    returnByValue: true,
  });
  hasHook = probe.result.value === true;
  if (!hasHook) {
    await new Promise(r => setTimeout(r, 500));
    pollTries++;
  }
}
console.log(hasHook
  ? '[æRTXrender] deterministic hook found after polling'
  : '[æRTXrender] WARNING: no __renderFrame hook — falling back to real-time capture');\n\n`;

const captureMarker = '// ── Capture ──';
if (!src.includes('Polling for the hook')) {
  src = src.replace(captureMarker, pollingCode + captureMarker);
  writeFileSync(RENDER_MJS, src);
  console.log('[render-io] patched render.mjs with hook polling');
}

const childArgs = [
  RENDER_MJS,
  `--url=${url}`,
  `--out=${out}`,
  `--frames=${frames}`,
  `--fps=${fps}`,
  `--w=${w}`,
  `--h=${h}`,
  `--encoder=${enc}`
];

console.log('[render-io] starting render…');
const child = spawn(NODE_EXE, childArgs, { stdio: 'inherit' });
child.on('exit', (code) => process.exit(code || 0));
child.on('error', (err) => { console.error('[render-io] spawn error:', err.message); process.exit(1); });
