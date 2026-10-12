// Inspect the live DOM structure: why does a.card count 8 when the source has 4?
const PORT = process.argv[2] || '9223';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function main() {
  const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
  const page = targets.find((t) => t.type === 'page' && t.url.includes('index.html'));
  if (!page) { console.log('NO_PAGE'); process.exit(2); }
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map();
  const send = (method, params) => new Promise((res) => { const m = ++id; pending.set(m, res); ws.send(JSON.stringify({ id: m, method, params })); });
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } }; });
  await send('Runtime.enable');
  const expr = `(() => {
    const cards = [...document.querySelectorAll('a.card')];
    const outer = document.querySelectorAll('.wrap > a.card').length;
    const nested = [...document.querySelectorAll('a a')].length;
    const wrapChildren = [...document.querySelector('.wrap').children].map(e => e.tagName + '.' + (e.className||'').split(' ')[0]);
    return JSON.stringify({
      aCardTotal: cards.length,
      wrapDirectCards: outer,
      nestedAnchors: nested,
      firstCardOuterHTML: cards[0] ? cards[0].outerHTML.slice(0, 220) : null,
      wrapChildren: wrapChildren.slice(0, 14),
      linksPerCard: cards.map(c => c.querySelectorAll('.links a').length)
    }, null, 1);
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
  console.log(r.result?.result?.value);
  ws.close(); process.exit(0);
}
main().catch((e) => { console.log('FAIL', e.message); process.exit(1); });
