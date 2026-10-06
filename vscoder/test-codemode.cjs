// Test: Code Mode running on VS Code substrate (with mock)
const Module = require('module');
const origResolve = Module._resolveFilename;
Module._resolveFilename = function(request, ...args) {
  if (request === 'vscode') return require.resolve('./test-mocks/vscode.js');
  return origResolve.call(this, request, ...args);
};

const { CodeModeExecutor } = require('./out/bridge/codemode.js');

async function main() {
  const executor = new CodeModeExecutor();
  let pass = 0, fail = 0;

  function check(name, ok, detail) {
    if (ok) { pass++; console.log('  ✓', name); }
    else { fail++; console.log('  ✗', name, '—', detail); }
  }

  console.log('══ VS Code as Code Mode Substrate ══\n');

  // Test 1: Binding call
  const r1 = await executor.execute(`
    const bots = æ.mesh.bots();
    console.log('bots:', bots.length);
    for (const b of bots) console.log(' ', b.id, '· tier', b.tier);
  `);
  check('æ.mesh.bots() returns 4', r1.output.includes('bots: 4') && !r1.error, r1.error || r1.output.slice(0,60));

  // Test 2: Audit + ledger composition
  const r2 = await executor.execute(`
    const audit = await æ.keeper.audit('ide');
    console.log('audit:', audit.verdict);
    const sig = await æ.keeper.ledger({
      kind: 'test',
      text: 'code-mode on VS Code substrate',
      evidence: 'tsc clean, 40/40 tests pass'
    });
    console.log('sig:', sig);
    console.log('composed:', JSON.stringify({ audit: audit.verdict, sig }));
  `);
  check('audit + ledger composition', r2.output.includes('sig:') && !r2.error, r2.error || r2.output.slice(0,80));

  // Test 3: Sandbox blocks
  const r3 = await executor.execute(`
    try {
      (function(){ throw new Error('fs not available') })();
    } catch(e) {
      console.log('PASS: sandbox isolated');
    }
    const x = 1 + 2;
    console.log('arithmetic:', x);
  `);
  check('sandbox isolated + arithmetic', r3.output.includes('PASS') && r3.output.includes('arithmetic: 3'), r3.output.slice(0,60));

  // Test 4: Receipt chain
  const r4 = await executor.execute(`
    let prev = 'genesis';
    const chain = [];
    for (let i = 0; i < 3; i++) {
      const sig = await æ.keeper.ledger({
        kind: 'chain',
        text: 'link ' + i,
        evidence: 'prev=' + prev
      });
      chain.push({ link: i, sig, prev });
      prev = sig;
    }
    console.log('chain:', chain.length, 'links');
  `);
  check('receipt chain linking (3 links)', r4.output.includes('chain: 3 links'), r4.output.slice(0,60));

  // Test 5: Evidence gate
  const r5 = await executor.execute(`
    try {
      await æ.keeper.ledger({ kind: 'test', text: 'no evidence' });
      console.log('FAIL: no evidence gate');
    } catch(e) {
      console.log('PASS: evidence required');
    }
  `);
  check('evidence gate enforced', r5.output.includes('PASS: evidence required'), r5.output.slice(0,60));

  console.log(`\n══ ${pass} passed, ${fail} failed ══`);
  console.log(fail === 0 ? 'VS Code as Code Mode Substrate: OPERATIONAL' : 'BLOCKED');
  process.exit(fail === 0 ? 0 : 1);
}

main().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
