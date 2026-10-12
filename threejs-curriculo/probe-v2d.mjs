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

// Capture console errors
await send('Runtime.enable');
await send('Log.enable');

await send('Page.navigate', {url: 'http://127.0.0.1:8124/internetofagents-v2.html'});
await new Promise(r => setTimeout(r, 5000));

// Check what's on the page
const check = await send('Runtime.evaluate', {
  expression: `JSON.stringify({
    url: location.href,
    title: document.title,
    bodyLen: document.body.innerHTML.length,
    meshGrid: !!document.getElementById('meshGrid'),
    receiptChain: !!document.getElementById('receiptChain'),
    qrTest: typeof qrcode,
    scriptCount: document.querySelectorAll('script').length
  })`,
  returnByValue: true
});
console.log('Page state:', check.result.value);

// Try executing the agent creation manually
const manual = await send('Runtime.evaluate', {
  expression: `(function() {
    try {
      const mg = document.getElementById('meshGrid');
      if (!mg) return 'no meshGrid';
      const node = document.createElement('div');
      node.className = 'agent-node';
      node.innerHTML = '<div class="name">test</div>';
      mg.appendChild(node);
      return 'manual append OK, children: ' + mg.children.length;
    } catch(e) {
      return 'error: ' + e.message;
    }
  })()`,
  returnByValue: true
});
console.log('Manual test:', manual.result.value);

ws.close();
process.exit(0);
