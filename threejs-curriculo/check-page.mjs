// Probe the internetofagents.html page and check for Three.js loading
const CDP_URL = await fetch('http://127.0.0.1:9333/json').then(r => r.json());
const page = CDP_URL.find(p => p.type === 'page');
console.log('Page:', page?.title, page?.url);

async function pageEval(expr) {
  const res = await fetch('http://127.0.0.1:9333/devtools/json/EDDE69DDEC4656F2D635785C8CA652FC', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      method: 'Runtime.evaluate',
      params: { expression: expr, returnByValue: true }
    })
  });
  const j = await res.json();
  return j.result?.result?.value;
}

const results = await Promise.all([
  pageEval(`typeof window.__renderFrame`),
  pageEval(`typeof THREE`),
  pageEval(`document.getElementById('mesh') ? 'canvas-found' : 'canvas-missing'`)
]);
console.log('Results:', JSON.stringify(results, null, 2));

// Check for console errors
const errors = [];
const client = await fetch('http://127.0.0.1:9333/devtools/json/EDDE69DDEC4656F2D635785C8CA652FC/console', { method: 'GET' });
console.log('Console:', await client.text().catch(() => 'n/a'));
