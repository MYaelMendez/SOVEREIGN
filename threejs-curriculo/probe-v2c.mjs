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

const check = await send('Runtime.evaluate', {
  expression: `JSON.stringify({
    qrcodeLower: typeof qrcode,
    qrcodeUpper: typeof QRCode,
    windowQR: typeof window.qrcode
  })`,
  returnByValue: true
});
console.log('Library check:', check.result.value);

// Test lowercase API
const test = await send('Runtime.evaluate', {
  expression: `(function() {
    try {
      const qr = qrcode(0, 'M');
      qr.addData('ae://peer?host=test&mesh=pc://mesh/test/local');
      qr.make();
      const html = qr.createSvgTag({cellSize: 4, margin: 2});
      return 'QR SVG generated: ' + html.length + ' chars';
    } catch(e) {
      return 'Error: ' + e.message;
    }
  })()`,
  returnByValue: true
});
console.log('QR test:', test.result.value);

ws.close();
process.exit(0);
