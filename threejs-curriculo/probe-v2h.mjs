const resp = await fetch('http://127.0.0.1:9333/json');
const targets = await resp.json();
const page = targets.find(t => t.type === 'page' && !t.url.startsWith('chrome-extension'));
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
const consoleMessages = [];
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
  if (msg.method === 'Runtime.exceptionThrown') {
    consoleMessages.push('EXC: ' + (msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text));
  }
};
await new Promise(r => ws.onopen = r);

await send('Runtime.enable');
await send('Page.enable');

// Force hard reload with cache bypass
await send('Network.enable');
await send('Network.setCacheDisabled', {cacheDisabled: true});
await send('Page.navigate', {url: 'http://127.0.0.1:8124/internetofagents-v2.html?nocache=' + Date.now()});
await new Promise(r => setTimeout(r, 5000));

const r1 = await send('Runtime.evaluate', {expression: `document.getElementById('meshGrid').children.length`, returnByValue: true});
console.log('meshGrid children:', r1.result.value);

const r2 = await send('Runtime.evaluate', {expression: `document.getElementById('receiptChain').children.length`, returnByValue: true});
console.log('receiptChain children:', r2.result.value);

const r3 = await send('Runtime.evaluate', {expression: `typeof AGENTS`, returnByValue: true});
console.log('AGENTS type:', r3.result.value);

console.log('Exceptions:', JSON.stringify(consoleMessages));

ws.close();
process.exit(0);
