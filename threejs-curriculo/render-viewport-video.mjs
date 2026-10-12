// render-viewport-video.mjs
// Renders viewport-video.html to viewport-video.webm using headless Chrome + CDP
// Uses MediaRecorder in-page for efficient capture

import { spawn } from 'child_process';
import { writeFileSync } from 'fs';

const CHROME_PATH = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PAGE_URL = 'http://127.0.0.1:8123/viewport-video.html';
const OUTPUT_FILE = 'C:/æ/threejs-curriculo/viewport-video.webm';
const DURATION_MS = 21000;
const FPS = 30;

// Start HTTP server
const server = spawn('python', ['-m', 'http.server', '8123', '--bind', '127.0.0.1'], {
  cwd: 'C:/æ/threejs-curriculo',
  stdio: 'ignore'
});

await new Promise(r => setTimeout(r, 2000));

// Launch Chrome
const chrome = spawn(CHROME_PATH, [
  '--headless=new',
  '--disable-gpu',
  '--no-sandbox',
  '--remote-debugging-port=9222',
  '--window-size=1280,720',
  '--autoplay-policy=no-user-gesture-required',
  'about:blank'
], { stdio: 'ignore' });

await new Promise(r => setTimeout(r, 3000));

// Connect to CDP
const listResp = await fetch('http://127.0.0.1:9222/json');
const targets = await listResp.json();
const pageTarget = targets.find(t => t.type === 'page');
if (!pageTarget) throw new Error('No page target found');

const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, { once: true });
  ws.addEventListener('error', reject, { once: true });
});

let msgId = 0;
const pending = new Map();

ws.addEventListener('message', (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  }
});

function send(method, params = {}) {
  return new Promise((resolve) => {
    const id = ++msgId;
    pending.set(id, resolve);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

// Navigate to page
await send('Page.enable');
await send('Page.navigate', { url: PAGE_URL });
await new Promise(r => setTimeout(r, 5000));

// Inject MediaRecorder script
const recorderScript = `
  (async () => {
    const canvas = document.querySelector('canvas');
    if (!canvas) return { error: 'No canvas found' };
    
    const stream = canvas.captureStream(${FPS});
    const recorder = new MediaRecorder(stream, {
      mimeType: 'video/webm;codecs=vp9',
      videoBitsPerSecond: 5000000
    });
    
    const chunks = [];
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    
    const done = new Promise(r => recorder.onstop = r);
    recorder.start(100);
    
    await new Promise(r => setTimeout(r, ${DURATION_MS}));
    recorder.stop();
    await done;
    
    const blob = new Blob(chunks, { type: 'video/webm' });
    const reader = new FileReader();
    const base64 = await new Promise(r => {
      reader.onload = () => r(reader.result.split(',')[1]);
      reader.readAsDataURL(blob);
    });
    
    return { base64, size: blob.size, chunks: chunks.length };
  })()
`;

console.log('Recording 21 seconds of video...');
const result = await send('Runtime.evaluate', {
  expression: recorderScript,
  awaitPromise: true,
  returnByValue: true,
  timeout: DURATION_MS + 5000
});

if (result.result?.exceptionDetails) {
  console.error('Error:', result.result.exceptionDetails.text);
  process.exit(1);
}

const data = result.result?.result?.value;
if (!data || data.error) {
  console.error('Recording failed:', data);
  process.exit(1);
}

console.log(`Captured ${data.chunks} chunks, ${data.size} bytes`);
const buffer = Buffer.from(data.base64, 'base64');
writeFileSync(OUTPUT_FILE, buffer);
console.log(`Saved to ${OUTPUT_FILE}`);

ws.close();
chrome.kill();
server.kill();
process.exit(0);
