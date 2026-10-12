export function add(a: number, b: number): number {
  return a + b;
}

export function multiply(a: number, b: number): number {
  return a * b;
}

export class Calculator {
  private history: Array<{ op: string; result: number }> = [];

  compute(op: 'add' | 'mul', a: number, b: number): number {
    const result = op === 'add' ? add(a, b) : multiply(a, b);
    this.history.push({ op, result });
    return result;
  }

  getHistory() {
    return [...this.history];
  }
}
