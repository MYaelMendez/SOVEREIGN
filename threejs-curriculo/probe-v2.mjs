import { spawn } from 'node:child_process';
const NODE = 'C:/Users/yaelm/AppData/Local/hermes/tools/node-26.7.0-win32-x64/node.exe';
const resp = await fetch('http://127.0.0.1:9333/json');
const targets = await resp.json();
const page = targets.find(t => t.type === 'page' && !t.url.startsWith('chrome-extension'));
if (!page) { console.log('NO PAGE'); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const i = ++id; pending.set(i, {resolve, reject});
    ws.send(JSON.stringify({id: i, method, params}));
  });
}
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const {resolve, reject} = pending.get(msg.id); pending.delete(msg.id);
    if (msg.error) reject(new Error(msg.error.message)); else resolve(msg.result);
  }
};
await new Promise(r => ws.onopen = r);

// Navigate to v2
await send('Page.navigate', {url: 'http://127.0.0.1:8124/internetofagents-v2.html'});
await new Promise(r => setTimeout(r, 4000));

// Check QR generation
const qrCheck = await send('Runtime.evaluate', {
  expression: `JSON.stringify({
    qrCanvases: document.querySelectorAll('.qr-wrap canvas').length,
    qrImages: document.querySelectorAll('.qr-wrap img').length,
    receiptRows: document.querySelectorAll('.receipt-row').length,
    agentNodes: document.querySelectorAll('.agent-node').length,
    hasRenderFrame: typeof window.__renderFrame === 'function',
    a2aFilled: document.getElementById('a2aContract').innerHTML.length > 50
  })`,
  returnByValue: true
});
console.log('QR check:', qrCheck.result.value);

// Check receipt hashes
const receiptCheck = await send('Runtime.evaluate', {
  expression: `JSON.stringify(Array.from(document.querySelectorAll('.receipt-row .hash')).map(h => h.textContent.slice(0, 16)))`,
  returnByValue: true
});
console.log('Receipt hashes:', receiptCheck.result.value);

// Check canvas animation
const canvasCheck = await send('Runtime.evaluate', {
  expression: `JSON.stringify({
    canvasW: document.getElementById('mesh').width,
    canvasH: document.getElementById('mesh').height
  })`,
  returnByValue: true
});
console.log('Canvas:', canvasCheck.result.value);

ws.close();
process.exit(0);
