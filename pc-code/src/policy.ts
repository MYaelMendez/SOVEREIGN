/**
 * PC://CODE v0.1 — Authority Policy Engine
 * 
 * Grants or denies capabilities based on effect class.
 * Default: LOCAL=true, DURABLE=true, EXTERNAL=false
 * No commit, no push, no credentials — EXTERNAL is denied by default.
 */

import type { EffectClass, PolicyEngine, Capability } from './stateMachine.js';

export class AuthorityPolicy implements PolicyEngine {
  grants: Map<EffectClass, boolean>;

  constructor() {
    this.grants = new Map([
      ['LOCAL', true],
      ['DURABLE', true],
      ['EXTERNAL', false],
    ]);
  }

  check(capability: Capability): boolean {
    return this.grants.get(capability.effect) ?? false;
  }

  setGrant(effect: EffectClass, granted: boolean): void {
    this.grants.set(effect, granted);
  }

  getGrants(): Record<EffectClass, boolean> {
    return {
      LOCAL: this.grants.get('LOCAL') ?? false,
      DURABLE: this.grants.get('DURABLE') ?? false,
      EXTERNAL: this.grants.get('EXTERNAL') ?? false,
    };
  }
}
