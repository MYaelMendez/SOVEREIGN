// probe_widget.mjs — verify the widget end-to-end over CDP (Node 26 global WebSocket).
const CDP = 9333;
(async () => {
  const list = await (await fetch(`http://127.0.0.1:${CDP}/json`)).json();
  const page = list.find(x => x.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pend = new Map();
  const send = (method, params = {}) => new Promise(res => {
    const i = ++id; pend.set(i, res);
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  ws.onmessage = d => {
    const m = JSON.parse(d.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result || m); pend.delete(m.id); }
  };
  await new Promise(r => ws.onopen = r);
  await send('Page.enable'); await send('Runtime.enable');
  const errs = [];
  ws.addEventListener('message', d => {
    const m = JSON.parse(d.data);
    if (m.method === 'Runtime.exceptionThrown') errs.push(m.params?.exceptionDetails?.text || 'exc');
  });
  await send('Page.navigate', { url: 'http://127.0.0.1:8123/widget/widget.html' });
  await new Promise(r => setTimeout(r, 6000));
  const ev = async (expr) => (await send('Runtime.evaluate',
    { expression: expr, returnByValue: true, awaitPromise: true })).result?.value;
  const out = {
    status: await ev("document.getElementById('wstatus').textContent"),
    hash: await ev("document.getElementById('whash').textContent"),
    hasCanvas: await ev("!!document.querySelector('#stage canvas')"),
    hasRenderFrame: await ev("typeof window.__renderFrame"),
    webgl: await ev("(()=>{const c=document.querySelector('#stage canvas');if(!c)return false;return !!(c.getContext('webgl2')||c.getContext('webgl'));})()"),
  };
  console.log(JSON.stringify({ ...out, exceptions: errs }, null, 2));
  ws.close();
})().catch(e => { console.log('PROBE_ERR', e.message); process.exit(1); });
