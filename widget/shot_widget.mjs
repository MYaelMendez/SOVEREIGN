// shot_widget.mjs — capture the running widget's canvas to a PNG (CDP).
import { writeFileSync } from 'fs';
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
  await send('Emulation.setDeviceMetricsOverride', { width: 720, height: 1280, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: 'http://127.0.0.1:8123/widget/widget.html' });
  await new Promise(r => setTimeout(r, 6000));
  // drive to a mid-timeline frame deterministically
  await send('Runtime.evaluate', { expression: 'window.__renderFrame && window.__renderFrame(140, 360)', awaitPromise: true });
  await new Promise(r => setTimeout(r, 800));
  const { data } = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('C:/æ/widget/widget-shot.png', Buffer.from(data, 'base64'));
  console.log('shot saved:', Buffer.from(data, 'base64').length, 'bytes');
  ws.close();
})().catch(e => { console.log('SHOT_ERR', e.message); process.exit(1); });
