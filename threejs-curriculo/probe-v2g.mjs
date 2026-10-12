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
  if (msg.method === 'Runtime.consoleAPICalled') {
    consoleMessages.push(msg.params.type + ': ' + msg.params.args.map(a => a.value || a.description).join(' '));
  }
  if (msg.method === 'Runtime.exceptionThrown') {
    consoleMessages.push('EXCEPTION: ' + JSON.stringify(msg.params.exceptionDetails.text) + ' ' + (msg.params.exceptionDetails.exception?.description || ''));
  }
};
await new Promise(r => ws.onopen = r);

await send('Runtime.enable');
await send('Page.enable');
await send('Log.enable');

await send('Page.navigate', {url: 'http://127.0.0.1:8124/internetofagents-v2.html'});
await new Promise(r => setTimeout(r, 5000));

console.log('Console messages:', JSON.stringify(consoleMessages, null, 2));

// Also check: is the script tag the one with qrcode.js src, or the inline one?
const scriptCheck = await send('Runtime.evaluate', {
  expression: `Array.from(document.querySelectorAll('script')).map(s => s.src || 'inline:' + s.textContent.length).join(' | ')`,
  returnByValue: true
});
console.log('Scripts:', scriptCheck.result.value);

ws.close();
process.exit(0);
