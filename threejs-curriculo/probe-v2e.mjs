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

await send('Page.navigate', {url: 'http://127.0.0.1:8124/internetofagents-v2.html'});
await new Promise(r => setTimeout(r, 5000));

// Check if the script ran - look for AGENTS array, receipt chain content
const check = await send('Runtime.evaluate', {
  expression: `JSON.stringify({
    hasAGENTS: typeof AGENTS !== 'undefined',
    agentsLen: typeof AGENTS !== 'undefined' ? AGENTS.length : 0,
    meshGridChildren: document.getElementById('meshGrid') ? document.getElementById('meshGrid').children.length : -1,
    receiptChildren: document.getElementById('receiptChain') ? document.getElementById('receiptChain').children.length : -1,
    statsChildren: document.getElementById('stats') ? document.getElementById('stats').children.length : -1,
    a2aLen: document.getElementById('a2aContract') ? document.getElementById('a2aContract').innerHTML.length : -1,
    toastText: document.getElementById('toast') ? document.getElementById('toast').textContent : 'none'
  })`,
  returnByValue: true
});
console.log('Deep check:', check.result.value);

ws.close();
process.exit(0);
