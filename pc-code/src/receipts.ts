/**
 * PC://CODE v0.1 — Receipt System with SHA-256 Hash Chain
 * 
 * Every capability execution produces a receipt. Each receipt contains:
 * - index: sequential number
 * - timestamp: execution time
 * - capability: name of the capability
 * - state: state machine state
 * - effect: effect class (LOCAL/DURABLE/EXTERNAL)
 * - input: instruction or input data
 * - output: result data
 * - prevHash: hash of previous receipt (chain)
 * - hash: SHA-256 of this receipt's content
 */

import { createHash } from 'crypto';
import type { Receipt, StateName, EffectClass } from './stateMachine.js';

const GENESIS_HASH = '0'.repeat(64);

export class ReceiptChain {
  private receipts: Receipt[] = [];
  private lastHash: string = GENESIS_HASH;

  addReceipt(
    capability: string,
    state: StateName,
    effect: EffectClass,
    input: string,
    output: string
  ): Receipt {
    const index = this.receipts.length;
    const timestamp = Date.now();
    const prevHash = this.lastHash;

    const receipt: Receipt = {
      index,
      timestamp,
      capability,
      state,
      effect,
      input: input.slice(0, 2000),
      output: output.slice(0, 2000),
      prevHash,
      hash: '',
    };

    receipt.hash = this.computeHash(receipt);
    this.receipts.push(receipt);
    this.lastHash = receipt.hash;
    return receipt;
  }

  private computeHash(receipt: Omit<Receipt, 'hash'>): string {
    const data = JSON.stringify({
      index: receipt.index,
      timestamp: receipt.timestamp,
      capability: receipt.capability,
      state: receipt.state,
      effect: receipt.effect,
      input: receipt.input,
      output: receipt.output,
      prevHash: receipt.prevHash,
    });
    return createHash('sha256').update(data).digest('hex');
  }

  verify(): boolean {
    for (let i = 0; i < this.receipts.length; i++) {
      const r = this.receipts[i];
      const expectedPrevHash = i === 0 ? GENESIS_HASH : this.receipts[i - 1].hash;
      if (r.prevHash !== expectedPrevHash) return false;
      const { hash, ...rest } = r;
      const computed = this.computeHash(rest);
      if (computed !== hash) return false;
    }
    return true;
  }

  getReceipts(): Receipt[] {
    return [...this.receipts];
  }

  getLastHash(): string {
    return this.lastHash;
  }

  get length(): number {
    return this.receipts.length;
  }
}
