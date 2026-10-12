// Verify the Rust WASM core in the live page: does it load AND verify something
// real (known SHA-256 vector + a manifest hash over actual artifact bytes)?
const PORT = process.argv[2] || '9223';
const WAIT = parseInt(process.argv[3] || '14000', 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  let page = null;
  for (let i = 0; i < 30 && !page; i++) {
    try {
      const ts = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
      page = ts.find((t) => t.type === 'page' && t.url.includes('index.html'));
    } catch (e) { /* not up yet */ }
    if (!page) await sleep(400);
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
    const out = { wasm: g('s-wasm'), gpu: g('s-gpu'), sys: g('s-sys'), three: g('s-three') };
    try {
      const m = await import('./wasm/dist/teologia_ai.js');
      await m.default();
      out.core_imported = true;
      out.core_version = m.platform_version();
      out.core_vector = m.sha256_hex(new TextEncoder().encode('abc')).slice(0,16);
      out.core_artifacts = JSON.parse(m.get_platform_state_json()).total_artifacts;
      out.core_payload = m.get_aqr_payload('mayor');
      const mf = await (await fetch('./platform-manifest.json', {cache:'no-store'})).json();
      const e = mf.artifacts.find(a => a.file === 'catecismo-mayor.html');
      const bytes = new Uint8Array(await (await fetch('./' + e.file, {cache:'no-store'})).arrayBuffer());
      out.e2e_match = m.sha256_hex(bytes) === e.sha256;
      out.e2e_prefix = m.sha256_hex(bytes).slice(0,16);
    } catch (err) { out.core_error = String(err && err.message || err); }
    return JSON.stringify(out, null, 1);
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  console.log(r.result?.result?.value || JSON.stringify(r.result));
  console.log('CONSOLE:', logs.length ? '' : '(clean)');
  for (const l of logs.slice(0, 15)) console.log('  ' + l);
  ws.close(); process.exit(0);
}
main().catch((e) => { console.log('FAIL', e.message); process.exit(1); });
