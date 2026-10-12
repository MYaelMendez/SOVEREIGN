// CDP-based real-time verification of the teologia.ai platform page.
// Connects to a headless Chrome with --remote-debugging-port and evaluates the
// live DOM after real GPU work has had time to complete.
// Node 22+ has a global WebSocket, so no dependencies are needed.
const PORT = process.argv[2] || '9223';
const URL_MATCH = process.argv[3] || 'index.html';
const WAIT_MS = parseInt(process.argv[4] || '9000', 10);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  // find the page target
  let targets = [];
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json`);
      targets = await res.json();
      if (targets.some((t) => t.type === 'page' && t.url.includes(URL_MATCH))) break;
    } catch (e) { /* not up yet */ }
    await sleep(300);
  }
  const page = targets.find((t) => t.type === 'page' && t.url.includes(URL_MATCH));
  if (!page) {
    console.log('NO_PAGE_TARGET');
    console.log(JSON.stringify(targets.map((t) => ({ type: t.type, url: t.url })), null, 1));
    process.exit(2);
  }

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  const send = (method, params) => new Promise((resolve) => {
    const mid = ++id;
    pending.set(mid, resolve);
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
  const consoleMsgs = [];

  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
      if (msg.method === 'Runtime.consoleAPICalled') {
        consoleMsgs.push(msg.params.type + ': ' +
          (msg.params.args || []).map((a) => a.value ?? a.description ?? a.type).join(' '));
      }
      if (msg.method === 'Runtime.exceptionThrown') {
        consoleMsgs.push('EXCEPTION: ' +
          (msg.params.exceptionDetails?.exception?.description ||
           msg.params.exceptionDetails?.text || 'unknown'));
      }
    };
  });

  await send('Runtime.enable');
  await send('Page.enable');
  await sleep(WAIT_MS); // real time for GPU readback + module resolution

  const expr = `(() => {
    const g = (id) => { const e = document.getElementById(id); return e ? (e.textContent || '').trim() + ' [' + (e.className||'') + ']' : null; };
    return JSON.stringify({
      gpu: g('s-gpu'), llm: g('s-llm'), sys: g('s-sys'), three: g('s-three'),
      cards: document.querySelectorAll('a.card').length,
      ask: document.querySelectorAll('button.ai').length,
      badge: document.querySelectorAll('svg.aqr').length,
      badgeRects: document.querySelectorAll('svg.aqr rect').length,
      gpuCanvasVisible: (() => { const c = document.getElementById('gpu'); return c ? getComputedStyle(c).display : null; })(),
      gpuCanvasW: (() => { const c = document.getElementById('gpu'); return c ? c.width : null; })(),
      chatOpen: document.getElementById('chat')?.classList.contains('open') ?? null,
      fab: !!document.getElementById('fab'),
      importmap: !!document.querySelector('script[type=importmap]'),
      gpuAdapter: typeof navigator.gpu !== 'undefined' ? 'api-present' : 'absent'
    });
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
  const val = r.result?.result?.value;
  console.log('DOM:', val);
  if (consoleMsgs.length) {
    console.log('CONSOLE:');
    for (const m of consoleMsgs.slice(0, 25)) console.log('  ' + m);
  } else {
    console.log('CONSOLE: (clean)');
  }
  ws.close();
  process.exit(0);
}
main().catch((e) => { console.log('FAIL:', e.message); process.exit(1); });
