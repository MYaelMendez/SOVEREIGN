// Verify WebLLM in the live page: does the module load, does CreateMLCEngine exist,
// and can we actually init a model (or honestly report failure)?
const PORT = process.argv[2] || '9223';
const WAIT = parseInt(process.argv[3] || '12000', 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  let page = null;
  for (let i = 0; i < 30 && !page; i++) {
    try {
      const ts = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
      page = ts.find((t) => t.type === 'page' && t.url.includes('index.html'));
    } catch (e) { /* not up yet */ }
    if (!page) await sleep(500);
  }
  if (!page) { console.log('NO_PAGE'); process.exit(2); }

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map(); const logs = [];
  const send = (m, p) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method: m, params: p })); });
  await new Promise((res, rej) => {
    ws.onopen = res; ws.onerror = rej;
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
      if (m.method === 'Runtime.consoleAPICalled') logs.push(m.params.type + ': ' + (m.params.args || []).map(a => a.value ?? a.description ?? a.type).join(' '));
      if (m.method === 'Runtime.exceptionThrown') logs.push('EXCEPTION: ' + (m.params.exceptionDetails?.exception?.description || m.params.exceptionDetails?.text || '?'));
    };
  });
  await send('Runtime.enable');
  await send('Page.enable');
  await send('Page.reload', { ignoreCache: true });
  await sleep(WAIT);

  const expr = `(async () => {
    const g = (id) => { const e = document.getElementById(id); return e ? (e.textContent||'').trim() + ' [' + (e.className||'') + ']' : null; };
    const out = { wasm: g('s-wasm'), gpu: g('s-gpu'), llm: g('s-llm'), sys: g('s-sys'), three: g('s-three') };

    // 1. Can we import the WebLLM module?
    try {
      const mod = await import('./vendor/webllm/web-llm.js');
      out.webllm_imported = true;
      out.has_CreateMLCEngine = typeof mod.CreateMLCEngine === 'function';
      out.model_count = mod.AppConfig?.model_list?.length || 'unknown';
    } catch (e) {
      out.webllm_imported = false;
      out.webllm_error = String(e?.message || e);
    }

    // 2. Does the page have the WebLLM UI elements?
    out.has_load_btn = !!document.getElementById('load');
    out.has_model_select = !!document.getElementById('model');
    out.has_chat_body = !!document.getElementById('chat-body');
    out.has_send_btn = !!document.getElementById('send');
    out.ask_buttons = document.querySelectorAll('button.ai').length;

    // 3. Badge check
    const aqr = document.querySelector('.aqr');
    if (aqr) {
      const svg = aqr.querySelector('svg');
      out.badge_rects = svg ? svg.querySelectorAll('rect').length : 0;
    }

    return JSON.stringify(out, null, 1);
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  console.log(r.result?.result?.value || JSON.stringify(r.result));
  console.log('CONSOLE:', logs.length ? '' : '(clean)');
  for (const l of logs.slice(0, 15)) console.log('  ' + l);
  ws.close(); process.exit(0);
}
main().catch((e) => { console.log('FAIL', e.message); process.exit(1); });
