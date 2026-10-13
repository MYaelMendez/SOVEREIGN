
const CDP = 9333;
(async () => {
  const t = await (await fetch(`http://127.0.0.1:${CDP}/json`)).json();
  const page = t.find(x => x.type === 'page');
  const ws = new (require('ws'))(page.webSocketDebuggerUrl);
  let id = 0; const pend = new Map();
  const send = (method, params={}) => new Promise(res => { const i = ++id; pend.set(i,res); ws.send(JSON.stringify({id:i,method,params})); });
  ws.on('message', d => { const m = JSON.parse(d); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result||m); pend.delete(m.id); } });
  await new Promise(r => ws.on('open', r));
  await send('Page.enable'); await send('Runtime.enable');
  await send('Page.navigate', {url:'http://127.0.0.1:8123/widget/widget.html'});
  await new Promise(r => setTimeout(r, 5000));
  const evalx = async (expr) => (await send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true})).result?.value;
  const status = await evalx("document.getElementById('wstatus').textContent");
  const hash   = await evalx("document.getElementById('whash').textContent");
  const canvas = await evalx("!!document.querySelector('#stage canvas')");
  const wasmLive = await evalx("typeof WebAssembly!=='undefined'");
  const errs = await evalx("window.__errs||'none'");
  console.log(JSON.stringify({status, hash, canvas, wasmLive}, null, 2));
  ws.close();
})().catch(e => { console.log('PROBE_ERR', e.message); process.exit(1); });
