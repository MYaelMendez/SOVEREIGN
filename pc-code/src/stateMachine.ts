/**
 * PC://CODE v0.1 — Deterministic State Machine
 * 
 * States: IDLE → OBSERVE → PLAN → VALIDATE_PLAN → EXECUTE → DIAGNOSTICS → BUILD → TEST → REVIEW_DIFF → COMPLETE
 * 
 * Each state transition is a capability with an effect class:
 * - LOCAL: read-only, no side effects
 * - DURABLE: modifies local workspace
 * - EXTERNAL: touches external systems (network, git remote, etc.)
 * 
 * No commit, no push, no credentials. The agent only knows capabilities.
 */

export type StateName =
  | 'IDLE'
  | 'OBSERVE'
  | 'PLAN'
  | 'VALIDATE_PLAN'
  | 'EXECUTE'
  | 'DIAGNOSTICS'
  | 'BUILD'
  | 'TEST'
  | 'REVIEW_DIFF'
  | 'COMPLETE';

export type EffectClass = 'LOCAL' | 'DURABLE' | 'EXTERNAL';

export interface Capability {
  name: string;
  effect: EffectClass;
  description: string;
  execute: (context: AgentContext) => Promise<CapabilityResult>;
}

export interface CapabilityResult {
  success: boolean;
  data?: unknown;
  error?: string;
  receipt?: Receipt;
}

export interface AgentContext {
  workspacePath: string;
  instruction: string;
  currentState: StateName;
  history: StateTransition[];
  receipts: Receipt[];
  policy: PolicyEngine;
  receiptChain: import('./receipts.js').ReceiptChain;
}

export interface StateTransition {
  from: StateName;
  to: StateName;
  capability: string;
  effect: EffectClass;
  timestamp: number;
  receiptHash: string;
}

export interface Receipt {
  index: number;
  timestamp: number;
  capability: string;
  state: StateName;
  effect: EffectClass;
  input: string;
  output: string;
  prevHash: string;
  hash: string;
}

export interface PolicyEngine {
  grants: Map<EffectClass, boolean>;
  check(capability: Capability): boolean;
}

export const STATE_ORDER: StateName[] = [
  'IDLE',
  'OBSERVE',
  'PLAN',
  'VALIDATE_PLAN',
  'EXECUTE',
  'DIAGNOSTICS',
  'BUILD',
  'TEST',
  'REVIEW_DIFF',
  'COMPLETE',
];

export function nextState(current: StateName): StateName | null {
  const idx = STATE_ORDER.indexOf(current);
  if (idx < 0 || idx >= STATE_ORDER.length - 1) return null;
  return STATE_ORDER[idx + 1];
}

export function prevState(current: StateName): StateName | null {
  const idx = STATE_ORDER.indexOf(current);
  if (idx <= 0) return null;
  return STATE_ORDER[idx - 1];
}
