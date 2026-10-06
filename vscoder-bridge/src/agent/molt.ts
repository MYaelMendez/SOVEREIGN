/**
 * VSCODER://BRIDGE — MOLT Strategy Competition Module
 *
 * MOLT = Multi-strategy Optimization via Lateral Thinking.
 * When a strategy fails, create an alternative strategy limited by the
 * same intent and authority envelope. Compete strategies in parallel,
 * select the best based on evidence, and reintegrate the winner.
 */

export interface Intent {
  goal: string;
  constraints: string[];
}

export interface AuthorityEnvelope {
  allowedActions: string[];
  deniedActions: string[];
  scope: string;
  maxIterations: number;
}

export interface StrategyContext {
  intent: Intent;
  authority: AuthorityEnvelope;
  priorEvidence: Evidence[];
  iteration: number;
}

export interface Evidence {
  metric: string;
  value: number;
  lowerIsBetter: boolean;
  timestamp: number;
}

export interface StrategyResult {
  success: boolean;
  evidence: Evidence[];
  error?: string;
  durationMs: number;
}

export interface Strategy {
  id: string;
  name: string;
  intent: Intent;
  authority: AuthorityEnvelope;
  execute: (context: StrategyContext) => Promise<StrategyResult>;
}

export interface CompetitionResult {
  winner: Strategy;
  results: Map<string, StrategyResult>;
  evidence: Evidence[];
  totalDurationMs: number;
}

export interface MoltConfig {
  maxAlternatives: number;
  strategyTimeoutMs: number;
  minImprovementThreshold: number;
}

const DEFAULT_CONFIG: MoltConfig = {
  maxAlternatives: 3,
  strategyTimeoutMs: 30_000,
  minImprovementThreshold: 0.01,
};

let _idCounter = 0;
function nextId(): string {
  _idCounter += 1;
  return `molt_${Date.now()}_${_idCounter}`;
}

function computeScore(evidence: Evidence[]): number {
  if (evidence.length === 0) return 0;
  let total = 0;
  for (const e of evidence) {
    const normalized = e.lowerIsBetter ? 1 / (1 + e.value) : e.value;
    total += normalized;
  }
  return total / evidence.length;
}

function cloneIntent(intent: Intent): Intent {
  return { goal: intent.goal, constraints: [...intent.constraints] };
}

function cloneAuthority(authority: AuthorityEnvelope): AuthorityEnvelope {
  return {
    allowedActions: [...authority.allowedActions],
    deniedActions: [...authority.deniedActions],
    scope: authority.scope,
    maxIterations: authority.maxIterations,
  };
}

export class MoltEngine {
  private config: MoltConfig;
  private strategies: Map<string, Strategy> = new Map();
  private competitionHistory: CompetitionResult[] = [];

  constructor(config: Partial<MoltConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  create(
    name: string,
    intent: Intent,
    authority: AuthorityEnvelope,
    execute: (context: StrategyContext) => Promise<StrategyResult>,
  ): Strategy {
    const strategy: Strategy = {
      id: nextId(),
      name,
      intent: cloneIntent(intent),
      authority: cloneAuthority(authority),
      execute,
    };
    this.strategies.set(strategy.id, strategy);
    return strategy;
  }

  async compete(strategies: Strategy[]): Promise<CompetitionResult> {
    const startTime = Date.now();
    const results = new Map<string, StrategyResult>();
    const allEvidence: Evidence[] = [];

    const executions = strategies.map(async (strategy) => {
      const context: StrategyContext = {
        intent: strategy.intent,
        authority: strategy.authority,
        priorEvidence: [],
        iteration: 1,
      };

      const result = await this.executeWithTimeout(
        strategy, context, this.config.strategyTimeoutMs,
      );

      if (!result.success) {
        const alternativeResults = await this.spawnAlternatives(strategy, context, result);
        for (const altResult of alternativeResults) {
          allEvidence.push(...altResult.evidence);
          if (altResult.success) {
            results.set(strategy.id, altResult);
            return;
          }
        }
        results.set(strategy.id, result);
      } else {
        results.set(strategy.id, result);
      }

      allEvidence.push(...result.evidence);
    });

    await Promise.all(executions);

    const winner = this.selectWinner(strategies, results);

    const competitionResult: CompetitionResult = {
      winner, results, evidence: allEvidence,
      totalDurationMs: Date.now() - startTime,
    };

    this.competitionHistory.push(competitionResult);
    return competitionResult;
  }

  select(competitionResult: CompetitionResult): Strategy {
    return this.selectWinner(
      Array.from(competitionResult.results.keys()).map((id) => this.strategies.get(id)!),
      competitionResult.results,
    );
  }

  selectWinner(strategies: Strategy[], results: Map<string, StrategyResult>): Strategy {
    let bestStrategy: Strategy | null = null;
    let bestScore = -Infinity;

    for (const strategy of strategies) {
      const result = results.get(strategy.id);
      if (!result) continue;
      const score = computeScore(result.evidence);
      if (score > bestScore) {
        bestScore = score;
        bestStrategy = strategy;
      }
    }

    if (!bestStrategy) throw new Error("MOLT: no strategies to select from");
    return bestStrategy;
  }

  reintegrate(competitionResult: CompetitionResult): { strategy: Strategy; baseline: Intent; authority: AuthorityEnvelope } {
    const winner = competitionResult.winner;
    const winnerResult = competitionResult.results.get(winner.id);

    if (!winnerResult) {
      throw new Error(`MOLT: winner strategy ${winner.id} has no result in competition`);
    }

    const baseline: Intent = cloneIntent(winner.intent);
    const authority: AuthorityEnvelope = cloneAuthority(winner.authority);

    for (const [id, strategy] of this.strategies) {
      if (strategy.intent.goal === winner.intent.goal && id !== winner.id) {
        this.strategies.delete(id);
      }
    }

    return { strategy: winner, baseline, authority };
  }

  private async spawnAlternatives(
    failedStrategy: Strategy,
    originalContext: StrategyContext,
    failureResult: StrategyResult,
  ): Promise<StrategyResult[]> {
    const alternatives: StrategyResult[] = [];
    const priorEvidence = [...originalContext.priorEvidence, ...failureResult.evidence];

    for (let i = 0; i < this.config.maxAlternatives; i++) {
      const alternative = this.createAlternative(failedStrategy, i + 1, priorEvidence);
      const context: StrategyContext = {
        intent: alternative.intent,
        authority: alternative.authority,
        priorEvidence,
        iteration: i + 2,
      };

      const result = await this.executeWithTimeout(alternative, context, this.config.strategyTimeoutMs);
      alternatives.push(result);

      if (result.success) break;
      priorEvidence.push(...result.evidence);
    }

    return alternatives;
  }

  private createAlternative(
    failedStrategy: Strategy,
    alternativeIndex: number,
    priorEvidence: Evidence[],
  ): Strategy {
    const alternativeName = `${failedStrategy.name}_alt${alternativeIndex}`;

    return this.create(
      alternativeName,
      failedStrategy.intent,
      failedStrategy.authority,
      async (context: StrategyContext): Promise<StrategyResult> => {
        const startTime = Date.now();
        try {
          const result = await failedStrategy.execute({ ...context, priorEvidence });
          if (!result.success) {
            return { ...result, durationMs: Date.now() - startTime };
          }
          return { ...result, durationMs: Date.now() - startTime };
        } catch (err) {
          return {
            success: false, evidence: [],
            error: err instanceof Error ? err.message : String(err),
            durationMs: Date.now() - startTime,
          };
        }
      },
    );
  }

  private async executeWithTimeout(
    strategy: Strategy,
    context: StrategyContext,
    timeoutMs: number,
  ): Promise<StrategyResult> {
    return new Promise<StrategyResult>((resolve) => {
      const timer = setTimeout(() => {
        resolve({
          success: false, evidence: [],
          error: `Strategy ${strategy.name} timed out after ${timeoutMs}ms`,
          durationMs: timeoutMs,
        });
      }, timeoutMs);

      strategy.execute(context)
        .then((result) => { clearTimeout(timer); resolve(result); })
        .catch((err) => {
          clearTimeout(timer);
          resolve({
            success: false, evidence: [],
            error: err instanceof Error ? err.message : String(err),
            durationMs: 0,
          });
        });
    });
  }

  getHistory(): CompetitionResult[] { return [...this.competitionHistory]; }
  getStrategies(): Strategy[] { return Array.from(this.strategies.values()); }
  clear(): void { this.strategies.clear(); this.competitionHistory = []; }
}

export async function molt(
  intent: Intent,
  authority: AuthorityEnvelope,
  strategies: Array<{ name: string; execute: (context: StrategyContext) => Promise<StrategyResult> }>,
  config?: Partial<MoltConfig>,
): Promise<{
  winner: Strategy;
  result: CompetitionResult;
  reintegrated: { strategy: Strategy; baseline: Intent; authority: AuthorityEnvelope };
}> {
  const engine = new MoltEngine(config);
  const createdStrategies = strategies.map((s) => engine.create(s.name, intent, authority, s.execute));
  const result = await engine.compete(createdStrategies);
  const winner = engine.select(result);
  const reintegrated = engine.reintegrate(result);
  return { winner, result, reintegrated };
}
