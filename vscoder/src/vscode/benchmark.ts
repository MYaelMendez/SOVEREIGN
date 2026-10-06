/**
 * VSCODER:// Benchmark Runner
 * Runs benchmarks via VS Code terminal API, collects metrics, generates receipts.
 */

import * as vscode from 'vscode';
import * as crypto from 'crypto';
import * as path from 'path';

// ─── Types ───────────────────────────────────────────────────────────────────

export interface BenchmarkOperation {
  /** Human-readable operation name */
  name: string;
  /** Shell command to execute */
  command: string;
  /** Working directory (defaults to workspace root) */
  cwd?: string;
  /** Environment variables to set */
  env?: Record<string, string>;
  /** Number of warmup iterations */
  warmupIterations?: number;
  /** Number of measured iterations */
  benchmarkIterations?: number;
}

export interface BenchmarkMetrics {
  /** p50 latency in milliseconds */
  latencyP50: number;
  /** p95 latency in milliseconds */
  latencyP95: number;
  /** Frames per second */
  fps: number;
  /** Peak VRAM usage in MB */
  vramMax: number;
  /** Average GPU utilization percentage */
  gpuUtilization: number;
}

export interface BenchmarkReceipt {
  /** Operation name */
  operation: string;
  /** ISO timestamp */
  timestamp: string;
  /** Collected metrics */
  metrics: BenchmarkMetrics;
  /** Raw terminal output */
  rawOutput: string;
  /** SHA-256 hash of this receipt */
  hash: string;
  /** Previous receipt hash for chain integrity */
  previousHash: string | null;
}

export interface BenchmarkResult {
  operation: BenchmarkOperation;
  metrics: BenchmarkMetrics;
  receipt: BenchmarkReceipt;
  success: boolean;
  error?: string;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const DEFAULT_WARMUP = 3;
const DEFAULT_ITERATIONS = 10;
const RECEIPT_STORAGE_KEY = 'vscoder.benchmark.receipts';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, Math.min(idx, sorted.length - 1))];
}

function computeHash(data: string): string {
  return crypto.createHash('sha256').update(data).digest('hex');
}

function getWorkspaceRoot(): string {
  const folders = vscode.workspace.workspaceFolders;
  if (folders && folders.length > 0) {
    return folders[0].uri.fsPath;
  }
  return process.cwd();
}

// ─── Output Parsing ──────────────────────────────────────────────────────────

/**
 * Parse benchmark output for metrics.
 * Supports JSON output and key-value pair formats.
 */
function parseMetrics(output: string): BenchmarkMetrics {
  // Try JSON first
  const jsonMatch = output.match(/\{[\s\S]*"latency"[\s\S]*\}/i);
  if (jsonMatch) {
    try {
      const data = JSON.parse(jsonMatch[0]);
      return {
        latencyP50: Number(data.latency_p50 ?? data.latencyP50 ?? data.p50 ?? 0),
        latencyP95: Number(data.latency_p95 ?? data.latencyP95 ?? data.p95 ?? 0),
        fps: Number(data.fps ?? 0),
        vramMax: Number(data.vram_max ?? data.vramMax ?? data.max_vram ?? 0),
        gpuUtilization: Number(data.gpu_util ?? data.gpuUtilization ?? data.gpu_utilization ?? 0),
      };
    } catch {
      // Fall through to key-value parsing
    }
  }

  // Key-value pair parsing
  const get = (key: string): number => {
    const re = new RegExp(`${key}[\\s:=]+([\\d.]+)`, 'i');
    const m = output.match(re);
    return m ? parseFloat(m[1]) : 0;
  };

  return {
    latencyP50: get('latency_p50|latencyP50|p50'),
    latencyP95: get('latency_p95|latencyP95|p95'),
    fps: get('fps'),
    vramMax: get('vram_max|vramMax|max_vram'),
    gpuUtilization: get('gpu_util|gpuUtilization|gpu_utilization'),
  };
}

/**
 * Parse latency samples from output for percentile calculation.
 * Looks for lines like "latency: 12.5ms" or JSON array of latencies.
 */
function parseLatencySamples(output: string): number[] {
  const samples: number[] = [];

  // Try JSON array
  const jsonArrMatch = output.match(/"latencies"\s*:\s*\[([\d\s.,]+)\]/i);
  if (jsonArrMatch) {
    const nums = jsonArrMatch[1].split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
    if (nums.length > 0) return nums;
  }

  // Line-by-line parsing
  const lines = output.split('\n');
  for (const line of lines) {
    const m = line.match(/latency[:\s]+([\d.]+)\s*ms/i);
    if (m) {
      samples.push(parseFloat(m[1]));
    }
  }

  return samples;
}

// ─── Receipt Generation ──────────────────────────────────────────────────────

function generateReceipt(
  operationName: string,
  metrics: BenchmarkMetrics,
  rawOutput: string,
  previousHash: string | null
): BenchmarkReceipt {
  const timestamp = new Date().toISOString();
  const data = JSON.stringify({ operationName, metrics, timestamp, previousHash });
  const hash = computeHash(data);

  return {
    operation: operationName,
    timestamp,
    metrics,
    rawOutput,
    hash,
    previousHash,
  };
}

// ─── Terminal Execution ──────────────────────────────────────────────────────

interface TerminalResult {
  output: string;
  exitCode: number | null;
}

/**
 * Execute a command in a VS Code terminal and capture output.
 */
function runInTerminal(
  command: string,
  cwd: string,
  env?: Record<string, string>
): Promise<TerminalResult> {
  return new Promise((resolve, reject) => {
    const terminal = vscode.window.createTerminal({
      name: `VSCODER Benchmark`,
      cwd,
      env: env ?? {},
    });

    let output = '';
    let exitCode: number | null = null;

    // Use VS Code's terminal API to send command and capture output
    terminal.show();

    // Send the command with a marker to detect completion
    const marker = `__VSCODER_BENCHMARK_DONE_${Date.now()}__`;
    const wrappedCommand = `${command}; echo "${marker}:$?"`;

    terminal.sendText(wrappedCommand);

    // Poll for output using terminal API
    const startTime = Date.now();
    const timeout = 300_000; // 5 minutes

    const pollInterval = setInterval(() => {
      // Access terminal output via VS Code API
      // Note: VS Code doesn't provide direct terminal output reading
      // We use a workaround: write output to a temp file and read it
      const elapsed = Date.now() - startTime;
      if (elapsed > timeout) {
        clearInterval(pollInterval);
        terminal.dispose();
        reject(new Error('Benchmark timed out after 5 minutes'));
      }
    }, 1000);

    // Since VS Code terminal API doesn't support reading output directly,
    // we use a different approach: run via child_process through terminal
    // For now, resolve with empty output as placeholder
    // In production, this would use a more sophisticated approach

    // Alternative: Use VS Code's task system or direct execution
    // For this implementation, we'll use a file-based approach

    setTimeout(() => {
      clearInterval(pollInterval);
      terminal.dispose();
      resolve({ output: '', exitCode: 0 });
    }, 100);
  });
}

// ─── Alternative: Direct Execution with Output Capture ───────────────────────

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

/**
 * Execute benchmark command and capture output.
 * Uses child_process for reliable output capture.
 */
async function executeBenchmark(
  command: string,
  cwd: string,
  env?: Record<string, string>
): Promise<TerminalResult> {
  try {
    const fullEnv = { ...process.env, ...env };
    const { stdout, stderr } = await execAsync(command, {
      cwd,
      env: fullEnv,
      timeout: 300_000,
      maxBuffer: 10 * 1024 * 1024, // 10MB
    });
    return { output: stdout + stderr, exitCode: 0 };
  } catch (err: any) {
    return {
      output: err.stdout ? err.stdout + err.stderr : err.message,
      exitCode: err.code ?? 1,
    };
  }
}

// ─── Main Benchmark Runner ───────────────────────────────────────────────────

/**
 * Run a benchmark on a given operation.
 * Collects latency p50/p95, FPS, VRAM max, GPU utilization.
 * Generates a receipt with hash chain integrity.
 */
export async function run(operation: BenchmarkOperation): Promise<BenchmarkResult> {
  const cwd = operation.cwd ?? getWorkspaceRoot();
  const warmup = operation.warmupIterations ?? DEFAULT_WARMUP;
  const iterations = operation.benchmarkIterations ?? DEFAULT_ITERATIONS;

  try {
    // Warmup phase
    for (let i = 0; i < warmup; i++) {
      await executeBenchmark(operation.command, cwd, operation.env);
    }

    // Benchmark phase - collect outputs from all iterations
    const allOutputs: string[] = [];
    const latencySamples: number[] = [];

    for (let i = 0; i < iterations; i++) {
      const result = await executeBenchmark(operation.command, cwd, operation.env);
      allOutputs.push(result.output);

      const samples = parseLatencySamples(result.output);
      latencySamples.push(...samples);
    }

    const combinedOutput = allOutputs.join('\n---\n');

    // Parse metrics from combined output
    const metrics = parseMetrics(combinedOutput);

    // If we have latency samples, compute percentiles
    if (latencySamples.length > 0) {
      latencySamples.sort((a, b) => a - b);
      metrics.latencyP50 = percentile(latencySamples, 50);
      metrics.latencyP95 = percentile(latencySamples, 95);
    }

    // Get previous receipt hash for chain
    const context = vscode.extensions.getExtension('vscoder.vscoder')?.exports?.context;
    let previousHash: string | null = null;
    if (context) {
      const receipts = (context.globalState.get(RECEIPT_STORAGE_KEY) as BenchmarkReceipt[]) ?? [];
      if (receipts.length > 0) {
        previousHash = receipts[receipts.length - 1].hash;
      }
    }

    // Generate receipt
    const receipt = generateReceipt(operation.name, metrics, combinedOutput, previousHash);

    // Store receipt
    if (context) {
      const receipts = (context.globalState.get(RECEIPT_STORAGE_KEY) as BenchmarkReceipt[]) ?? [];
      receipts.push(receipt);
      await context.globalState.update(RECEIPT_STORAGE_KEY, receipts);
    }

    return {
      operation,
      metrics,
      receipt,
      success: true,
    };
  } catch (err: any) {
    return {
      operation,
      metrics: { latencyP50: 0, latencyP95: 0, fps: 0, vramMax: 0, gpuUtilization: 0 },
      receipt: generateReceipt(operation.name, { latencyP50: 0, latencyP95: 0, fps: 0, vramMax: 0, gpuUtilization: 0 }, '', null),
      success: false,
      error: err.message,
    };
  }
}

// ─── Receipt Retrieval ───────────────────────────────────────────────────────

/**
 * Get all stored benchmark receipts.
 */
export function getReceipts(): BenchmarkReceipt[] {
  const context = vscode.extensions.getExtension('vscoder.vscoder')?.exports?.context;
  if (context) {
    const receipts = context.globalState.get(RECEIPT_STORAGE_KEY);
    return Array.isArray(receipts) ? receipts : [];
  }
  return [];
}

/**
 * Verify receipt chain integrity.
 */
export function verifyReceiptChain(receipts: BenchmarkReceipt[]): boolean {
  for (let i = 1; i < receipts.length; i++) {
    if (receipts[i].previousHash !== receipts[i - 1].hash) {
      return false;
    }
  }
  return true;
}

// ─── Default Export ──────────────────────────────────────────────────────────

export default {
  run,
  getReceipts,
  verifyReceiptChain,
};
