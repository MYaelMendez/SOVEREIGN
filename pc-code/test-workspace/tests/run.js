const { add, multiply, Calculator } = require('../src/calc');

let passed = 0;
let failed = 0;

function assert(condition, msg) {
  if (condition) { passed++; console.log('  PASS: ' + msg); }
  else { failed++; console.error('  FAIL: ' + msg); }
}

console.log('Test Suite: calc');

assert(add(2, 3) === 5, 'add(2,3) === 5');
assert(add(-1, 1) === 0, 'add(-1,1) === 0');
assert(multiply(3, 4) === 12, 'multiply(3,4) === 12');
assert(multiply(0, 5) === 0, 'multiply(0,5) === 0');

const calc = new Calculator();
assert(calc.compute('add', 10, 20) === 30, 'Calculator.add(10,20) === 30');
assert(calc.compute('mul', 6, 7) === 42, 'Calculator.mul(6,7) === 42');
assert(calc.getHistory().length === 2, 'history length === 2');

console.log('\nResults: ' + passed + ' passed, ' + failed + ' failed');
process.exit(failed > 0 ? 1 : 0);
