// live_widget.mjs — capture the widget running LIVE, plus a frame sequence to prove motion.
import { writeFileSync } from 'fs';
const CDP = 9333;
(async () => {
  const list = await (await fetch(`http://127.0.0.1:${CDP}/json`)).json();
  const page = list.find(x => x.type === 'page');
  if (!page) throw new Error('no page target on ' + CDP);
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
  await send('Emulation.setDeviceMetricsOverride', { width: 720, height: 1280, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: 'http://127.0.0.1:8123/widget/widget.html' });
  await new Promise(r => setTimeout(r, 7000));

  const ev = async (expr) => (await send('Runtime.evaluate',
    { expression: expr, returnByValue: true, awaitPromise: true })).result?.value;

  // prove the runtime is live
  const status = await ev("document.getElementById('wstatus').textContent");
  const hash = await ev("document.getElementById('whash').textContent");
  console.log('STATUS:', status, '| HASH:', hash);

  // capture a sequence of deterministic frames -> prove motion (the WASM drives it)
  const frames = [0, 60, 120, 180, 240, 300, 359];
  const shots = [];
  for (const f of frames) {
    await send('Runtime.evaluate', { expression: `window.__renderFrame(${f},360)`, awaitPromise: true });
    await new Promise(r => setTimeout(r, 150));
    const { data } = await send('Page.captureScreenshot', { format: 'png' });
    const buf = Buffer.from(data, 'base64');
    const p = `C:/æ/widget/live/frame_${String(f).padStart(3,'0')}.png`;
    writeFileSync(p, buf);
    shots.push({ f, bytes: buf.length });
  }
  console.log('FRAMES:', JSON.stringify(shots));
  // one hero shot at a mid frame
  await send('Runtime.evaluate', { expression: 'window.__renderFrame(140,360)', awaitPromise: true });
  await new Promise(r => setTimeout(r, 300));
  const { data } = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('C:/æ/widget/widget-LIVE.png', Buffer.from(data, 'base64'));
  console.log('HERO saved:', Buffer.from(data, 'base64').length, 'bytes');
  ws.close();
})().catch(e => { console.log('ERR', e.message); process.exit(1); });
