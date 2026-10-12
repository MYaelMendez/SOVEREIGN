// Reload the page under CDP, wait real time, then verify structure + compute.
const PORT = process.argv[2] || '9223';
const WAIT = parseInt(process.argv[3] || '11000', 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
  const page = targets.find((t) => t.type === 'page' && t.url.includes('index.html'));
  if (!page) { console.log('NO_PAGE'); process.exit(2); }
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map(); const consoleMsgs = [];
  const send = (method, params) => new Promise((res) => { const m = ++id; pending.set(m, res); ws.send(JSON.stringify({ id: m, method, params })); });
  await new Promise((res, rej) => {
    ws.onopen = res; ws.onerror = rej;
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
      if (m.method === 'Runtime.consoleAPICalled') consoleMsgs.push(m.params.type + ': ' + (m.params.args || []).map((a) => a.value ?? a.description ?? a.type).join(' '));
      if (m.method === 'Runtime.exceptionThrown') consoleMsgs.push('EXCEPTION: ' + (m.params.exceptionDetails?.exception?.description || m.params.exceptionDetails?.text || '?'));
    };
  });
  await send('Runtime.enable');
  await send('Page.enable');
  await send('Page.reload', { ignoreCache: true });
  await sleep(WAIT);

  const expr = `(() => {
    const g = (id) => { const e = document.getElementById(id); return e ? (e.textContent || '').trim() + ' [' + (e.className||'') + ']' : null; };
    const cards = [...document.querySelectorAll('.card')];
    return JSON.stringify({
      gpu: g('s-gpu'), llm: g('s-llm'), sys: g('s-sys'), three: g('s-three'),
      cards: cards.length,
      cardsInWrap: document.querySelectorAll('.wrap > .card').length,
      linksPerCard: cards.map(c => c.querySelectorAll('.links a, .links button').length),
      ask: document.querySelectorAll('button.ai').length,
      nestedAnchors: document.querySelectorAll('a a').length,
      badge: document.querySelectorAll('svg.aqr').length,
      badgeRects: document.querySelectorAll('svg.aqr rect').length,
      gpuCanvas: (() => { const c = document.getElementById('gpu'); return c ? getComputedStyle(c).display + '/' + c.width : null; })(),
      fab: !!document.getElementById('fab'),
      chat: !!document.getElementById('chat')
    });
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
  console.log('DOM:', r.result?.result?.value);
  console.log('CONSOLE:', consoleMsgs.length ? '' : '(clean)');
  for (const m of consoleMsgs.slice(0, 20)) console.log('  ' + m);
  ws.close(); process.exit(0);
}
main().catch((e) => { console.log('FAIL', e.message); process.exit(1); });
