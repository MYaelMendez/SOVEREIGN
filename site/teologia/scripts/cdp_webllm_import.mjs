// Verify the vendored WebLLM ESM actually imports in the browser context and
// exposes CreateMLCEngine + the model list. HTTP 200 is not proof of import.
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

  const expr = `(async () => {
    try {
      const t0 = performance.now();
      const mod = await import('./vendor/webllm/web-llm.js');
      const ms = Math.round(performance.now() - t0);
      return JSON.stringify({
        imported: true,
        ms,
        hasCreateMLCEngine: typeof mod.CreateMLCEngine === 'function',
        hasPrebuiltAppConfig: !!mod.prebuiltAppConfig,
        modelCount: mod.prebuiltAppConfig?.model_list?.length ?? null,
        hasSmallModel: (mod.prebuiltAppConfig?.model_list || []).some(m => /SmolLM2-360M-Instruct-q4f16_1-MLC/.test(m.model_id)),
        exports: Object.keys(mod).length
      });
    } catch (e) {
      return JSON.stringify({ imported: false, error: String(e && e.message || e) });
    }
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  console.log('WEBLLM IMPORT:', r.result?.result?.value);
  ws.close(); process.exit(0);
}
main().catch((e) => { console.log('FAIL', e.message); process.exit(1); });
