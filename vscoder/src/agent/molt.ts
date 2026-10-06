/**
 * MOLT() Strategy Competition Module for VSCODER://
 *
 * MOLT = Multi-strategy Optimization via Lateral Thinking.
 *
 * When a strategy fails, create an alternative strategy limited by the
 * same intent and authority envelope. Compete strategies in parallel,
 * select the best based on evidence, and reintegrate the winner.
 *
 * Core invariant: every alternative strategy shares the original intent
 * and authority envelope — only the execution approach differs.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** What a strategy is trying to achieve. */
export interface Intent {
  /** Human-readable goal description. */
  goal: string;
  /** Hard constraints the strategy must respect. */
  constraints: string[];
}

/** What a strategy is allowed to do — its authority envelope. */
export interface AuthorityEnvelope {
  /** Actions the strategy may perform. */
  allowedActions: string[];
  /** Actions the strategy must never perform. */
  deniedActions: string[];
  /** Scope boundary (e.g., file path, module name, API endpoint). */
  scope: string;
  /** Maximum iterations before the strategy is considered failed. */
  maxIterations: number;
}

/** Runtime context passed to a strategy's execute function. */
export interface StrategyContext {
  intent: Intent;
  authority: AuthorityEnvelope;
  /** Evidence accumulated from prior attempts (for alternative strategies). */
  priorEvidence: Evidence[];
  /** Current iteration number (1-based). */
  iteration: number;
}

/** A single piece of measurable evidence produced by a strategy. */
export interface Evidence {
  /** Metric name (e.g., "coverage", "latency_ms", "error_rate"). */
  metric: string;
  /** Numeric value; higher is better unless `lowerIsBetter` is set. */
  value: number;
  /** Whether lower values are better for this metric. */
  lowerIsBetter: boolean;
  /** When the evidence was produced (epoch ms). */
  timestamp: number;
}

/** Result of executing a single strategy. */
export interface StrategyResult {
  /** Whether the strategy completed successfully. */
  success: boolean;
  /** Evidence produced during execution. */
  evidence: Evidence[];
  /** Error message if the strategy failed. */
  error?: string;
  /** Wall-clock execution time in milliseconds. */
  durationMs: number;
}

/** A competing strategy. */
export interface Strategy {
  /** Unique identifier. */
  id: string;
  /** Human-readable name. */
  name: string;
  /** The intent this strategy pursues. */
  intent: Intent;
  /** The authority envelope this strategy operates within. */
  authority: AuthorityEnvelope;
  /** Execute the strategy and return its result. */
  execute: (context: StrategyContext) => Promise<StrategyResult>;
}

/** Result of a competition among multiple strategies. */
export interface CompetitionResult {
  /** The winning strategy (highest evidence score). */
  winner: Strategy;
  /** Per-strategy results keyed by strategy ID. */
  results: Map<string, StrategyResult>;
  /** Aggregated evidence across all strategies. */
  evidence: Evidence[];
  /** Total wall-clock time for the competition in milliseconds. */
  totalDurationMs: number;
}

/** Configuration for the MOLT competition engine. */
export interface MoltConfig {
  /** Maximum number of alternative strategies to spawn on failure. */
  maxAlternatives: number;
  /** Timeout per strategy in milliseconds. */
  strategyTimeoutMs: number;
  /** Minimum evidence score improvement to accept an alternative. */
  minImprovementThreshold: number;
}

// ---------------------------------------------------------------------------
// Default configuration
// ---------------------------------------------------------------------------

const DEFAULT_CONFIG: MoltConfig = {
  maxAlternatives: 3,
  strategyTimeoutMs: 30_000,
  minImprovementThreshold: 0.01,
};

// ---------------------------------------------------------------------------
// Utility: generate unique IDs
// ---------------------------------------------------------------------------

let _idCounter = 0;
function nextId(): string {
  _idCounter += 1;
  return `molt_${Date.now()}_${_idCounter}`;
}

// ---------------------------------------------------------------------------
// Utility: compute evidence score
// ---------------------------------------------------------------------------

/**
 * Compute a normalized score from a set of evidence.
 * Returns a value in [0, 1] where 1 is best.
 */
function computeScore(evidence: Evidence[]): number {
  if (evidence.length === 0) return 0;
  let total = 0;
  for (const e of evidence) {
    // Normalize: if lowerIsBetter, invert the value
    const normalized = e.lowerIsBetter ? 1 / (1 + e.value) : e.value;
    total += normalized;
  }
  return total / evidence.length;
}

// ---------------------------------------------------------------------------
// Utility: deep clone intent and authority (for alternative strategies)
// ---------------------------------------------------------------------------

function cloneIntent(intent: Intent): Intent {
  return {
    goal: intent.goal,
    constraints: [...intent.constraints],
  };
}

function cloneAuthority(authority: AuthorityEnvelope): AuthorityEnvelope {
  return {
    allowedActions: [...authority.allowedActions],
    deniedActions: [...authority.deniedActions],
    scope: authority.scope,
    maxIterations: authority.maxIterations,
  };
}

// ---------------------------------------------------------------------------
// MOLT Engine
// ---------------------------------------------------------------------------

export class MoltEngine {
  private config: MoltConfig;
  private strategies: Map<string, Strategy> = new Map();
  private competitionHistory: CompetitionResult[] = [];

  constructor(config: Partial<MoltConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  // -------------------------------------------------------------------------
  // molt.create — create a new strategy
  // -------------------------------------------------------------------------

  /**
   * Create a new strategy with the given intent and authority envelope.
   * The strategy's execute function will be called during competition.
   */
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

  // -------------------------------------------------------------------------
  // molt.compete — run multiple strategies in parallel
  // -------------------------------------------------------------------------

  /**
   * Run multiple strategies in parallel and return the competition result.
   * Each strategy receives a context with the shared intent and authority.
   * If a strategy fails, alternative strategies are automatically spawned
   * (limited by the same intent and authority envelope) up to `maxAlternatives`.
   */
  async compete(strategies: Strategy[]): Promise<CompetitionResult> {
    const startTime = Date.now();
    const results = new Map<string, StrategyResult>();
    const allEvidence: Evidence[] = [];

    // Run all strategies in parallel with timeout
    const executions = strategies.map(async (strategy) => {
      const context: StrategyContext = {
        intent: strategy.intent,
        authority: strategy.authority,
        priorEvidence: [],
        iteration: 1,
      };

      const result = await this.executeWithTimeout(
        strategy,
        context,
        this.config.strategyTimeoutMs,
      );

      // If the strategy failed, spawn alternatives (MOLT pattern)
      if (!result.success) {
        const alternativeResults = await this.spawnAlternatives(
          strategy,
          context,
          result,
        );
        // Merge alternative evidence
        for (const altResult of alternativeResults) {
          allEvidence.push(...altResult.evidence);
          if (altResult.success) {
            // Alternative succeeded — use its result
            results.set(strategy.id, altResult);
            return;
          }
        }
        // All alternatives failed too — keep original failure
        results.set(strategy.id, result);
      } else {
        results.set(strategy.id, result);
      }

      allEvidence.push(...result.evidence);
    });

    await Promise.all(executions);

    // Select winner based on evidence
    const winner = this.selectWinner(strategies, results);

    const competitionResult: CompetitionResult = {
      winner,
      results,
      evidence: allEvidence,
      totalDurationMs: Date.now() - startTime,
    };

    this.competitionHistory.push(competitionResult);
    return competitionResult;
  }

  // -------------------------------------------------------------------------
  // molt.select — select the best strategy based on evidence
  // -------------------------------------------------------------------------

  /**
   * Select the best strategy from a competition result based on evidence score.
   * Returns the strategy with the highest evidence score.
   */
  select(competitionResult: CompetitionResult): Strategy {
    return this.selectWinner(
      Array.from(competitionResult.results.keys()).map(
        (id) => this.strategies.get(id)!,
      ),
      competitionResult.results,
    );
  }

  /**
   * Select the best strategy from a set of strategies and their results.
   */
  selectWinner(
    strategies: Strategy[],
    results: Map<string, StrategyResult>,
  ): Strategy {
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

    if (!bestStrategy) {
      throw new Error("MOLT: no strategies to select from");
    }

    return bestStrategy;
  }

  // -------------------------------------------------------------------------
  // molt.reintegrate — reintegrate the winning strategy
  // -------------------------------------------------------------------------

  /**
   * Reintegrate the winning strategy into the active strategy registry.
   * The winning strategy's approach becomes the new baseline for the
   * given intent and authority envelope.
   */
  reintegrate(
    competitionResult: CompetitionResult,
  ): { strategy: Strategy; baseline: Intent; authority: AuthorityEnvelope } {
    const winner = competitionResult.winner;
    const winnerResult = competitionResult.results.get(winner.id);

    if (!winnerResult) {
      throw new Error(
        `MOLT: winner strategy ${winner.id} has no result in competition`,
      );
    }

    // The winner's intent and authority become the new baseline
    const baseline: Intent = cloneIntent(winner.intent);
    const authority: AuthorityEnvelope = cloneAuthority(winner.authority);

    // Remove all previous strategies with the same intent goal
    // and replace with the winner
    for (const [id, strategy] of this.strategies) {
      if (
        strategy.intent.goal === winner.intent.goal &&
        id !== winner.id
      ) {
        this.strategies.delete(id);
      }
    }

    return { strategy: winner, baseline, authority };
  }

  // -------------------------------------------------------------------------
  // Internal: spawn alternative strategies (MOLT pattern)
  // -------------------------------------------------------------------------

  /**
   * When a strategy fails, create alternative strategies limited by the
   * same intent and authority envelope. This is the core MOLT() pattern:
   * the alternative must pursue the same goal with the same permissions.
   */
  private async spawnAlternatives(
    failedStrategy: Strategy,
    originalContext: StrategyContext,
    failureResult: StrategyResult,
  ): Promise<StrategyResult[]> {
    const alternatives: StrategyResult[] = [];
    const priorEvidence = [
      ...originalContext.priorEvidence,
      ...failureResult.evidence,
    ];

    for (let i = 0; i < this.config.maxAlternatives; i++) {
      const alternative = this.createAlternative(
        failedStrategy,
        i + 1,
        priorEvidence,
      );

      const context: StrategyContext = {
        intent: alternative.intent,
        authority: alternative.authority,
        priorEvidence,
        iteration: i + 2, // iteration 1 was the original
      };

      const result = await this.executeWithTimeout(
        alternative,
        context,
        this.config.strategyTimeoutMs,
      );

      alternatives.push(result);

      if (result.success) {
        // Alternative succeeded — no need to spawn more
        break;
      }

      // Accumulate evidence for the next alternative
      priorEvidence.push(...result.evidence);
    }

    return alternatives;
  }

  /**
   * Create an alternative strategy based on a failed one.
   * The alternative shares the same intent and authority envelope
   * but uses a different execution approach.
   */
  private createAlternative(
    failedStrategy: Strategy,
    alternativeIndex: number,
    priorEvidence: Evidence[],
  ): Strategy {
    // The alternative strategy wraps the original but modifies its behavior
    // based on prior evidence. In practice, this could use different
    // algorithms, different parameters, or different execution paths.
    const alternativeName = `${failedStrategy.name}_alt${alternativeIndex}`;

    return this.create(
      alternativeName,
      failedStrategy.intent,
      failedStrategy.authority,
      async (context: StrategyContext): Promise<StrategyResult> => {
        const startTime = Date.now();

        try {
          // Execute the original strategy's logic with awareness of prior failures
          const result = await failedStrategy.execute({
            ...context,
            priorEvidence,
          });

          // If this alternative also fails, return the failure
          if (!result.success) {
            return {
              ...result,
              durationMs: Date.now() - startTime,
            };
          }

          // Success — return with updated duration
          return {
            ...result,
            durationMs: Date.now() - startTime,
          };
        } catch (err) {
          return {
            success: false,
            evidence: [],
            error: err instanceof Error ? err.message : String(err),
            durationMs: Date.now() - startTime,
          };
        }
      },
    );
  }

  // -------------------------------------------------------------------------
  // Internal: execute with timeout
  // -------------------------------------------------------------------------

  private async executeWithTimeout(
    strategy: Strategy,
    context: StrategyContext,
    timeoutMs: number,
  ): Promise<StrategyResult> {
    return new Promise<StrategyResult>((resolve) => {
      const timer = setTimeout(() => {
        resolve({
          success: false,
          evidence: [],
          error: `Strategy ${strategy.name} timed out after ${timeoutMs}ms`,
          durationMs: timeoutMs,
        });
      }, timeoutMs);

      strategy
        .execute(context)
        .then((result) => {
          clearTimeout(timer);
          resolve(result);
        })
        .catch((err) => {
          clearTimeout(timer);
          resolve({
            success: false,
            evidence: [],
            error: err instanceof Error ? err.message : String(err),
            durationMs: Date.now() - context.iteration * 0, // approximate
          });
        });
    });
  }

  // -------------------------------------------------------------------------
  // Public: get competition history
  // -------------------------------------------------------------------------

  getHistory(): CompetitionResult[] {
    return [...this.competitionHistory];
  }

  // -------------------------------------------------------------------------
  // Public: get all registered strategies
  // -------------------------------------------------------------------------

  getStrategies(): Strategy[] {
    return Array.from(this.strategies.values());
  }

  // -------------------------------------------------------------------------
  // Public: clear all strategies and history
  // -------------------------------------------------------------------------

  clear(): void {
    this.strategies.clear();
    this.competitionHistory = [];
  }
}

// ---------------------------------------------------------------------------
// Convenience: standalone MOLT() function for simple use cases
// ---------------------------------------------------------------------------

/**
 * Run a complete MOLT() cycle: create strategies, compete, select, reintegrate.
 * This is the high-level entry point for the MOLT pattern.
 */
export async function molt(
  intent: Intent,
  authority: AuthorityEnvelope,
  strategies: Array<{
    name: string;
    execute: (context: StrategyContext) => Promise<StrategyResult>;
  }>,
  config?: Partial<MoltConfig>,
): Promise<{
  winner: Strategy;
  result: CompetitionResult;
  reintegrated: { strategy: Strategy; baseline: Intent; authority: AuthorityEnvelope };
}> {
  const engine = new MoltEngine(config);

  // Create all strategies
  const createdStrategies = strategies.map((s) =>
    engine.create(s.name, intent, authority, s.execute),
  );

  // Compete
  const result = await engine.compete(createdStrategies);

  // Select winner
  const winner = engine.select(result);

  // Reintegrate
  const reintegrated = engine.reintegrate(result);

  return { winner, result, reintegrated };
}

// Types are already exported via their `export interface` declarations above.
