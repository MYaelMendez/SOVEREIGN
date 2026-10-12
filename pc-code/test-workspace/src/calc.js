function add(a, b) {
  return a + b;
}

function multiply(a, b) {
  return a * b;
}

class Calculator {
  constructor() {
    this.history = [];
  }

  compute(op, a, b) {
    const result = op === 'add' ? add(a, b) : multiply(a, b);
    this.history.push({ op, result });
    return result;
  }

  getHistory() {
    return [...this.history];
  }
}

module.exports = { add, multiply, Calculator };
