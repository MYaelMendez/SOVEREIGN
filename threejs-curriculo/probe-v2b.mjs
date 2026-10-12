import { spawn } from 'node:child_process';
const resp = await fetch('http://127.0.0.1:9333/json');
const targets = await resp.json();
const page = targets.find(t => t.type === 'page' && !t.url.startsWith('chrome-extension'));
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

// Check for JS errors
const errors = await send('Runtime.evaluate', {
  expression: `window.__jsErrors ? JSON.stringify(window.__jsErrors) : 'no errors captured'`,
  returnByValue: true
});
console.log('Errors:', errors.result.value);

// Check QRCode library loaded
const qrLib = await send('Runtime.evaluate', {
  expression: `typeof QRCode`,
  returnByValue: true
});
console.log('QRCode type:', qrLib.result.value);

// Try to run the QR generation manually
const qrTest = await send('Runtime.evaluate', {
  expression: `(function() {
    try {
      const el = document.getElementById('meshGrid');
      if (!el) return 'no meshGrid element';
      el.innerHTML = '<div id="qrtest" style="width:128px;height:128px"></div>';
      new QRCode(document.getElementById('qrtest'), {text: 'ae://peer?host=test', width: 128, height: 128});
      return 'QR generated: ' + document.getElementById('qrtest').innerHTML.length + ' chars';
    } catch(e) {
      return 'QR error: ' + e.message;
    }
  })()`,
  returnByValue: true
});
console.log('QR test:', qrTest.result.value);

ws.close();
process.exit(0);
