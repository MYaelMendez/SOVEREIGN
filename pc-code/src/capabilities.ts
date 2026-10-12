/**
 * PC://CODE v0.1 — WebMCP Capabilities
 * 
 * 8 tools: workspace_inspect, symbol_find, symbol_references, diagnostics_read,
 *         build_run, test_run, git_diff, receipt_verify
 * 
 * Each capability has an effect class and is routed through the policy engine.
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import type { Capability, AgentContext, CapabilityResult, EffectClass } from './stateMachine.js';
import type { ReceiptChain } from './receipts.js';

// ─── workspace_inspect (LOCAL) ───────────────────────────────────────────────

export const workspaceInspect: Capability = {
  name: 'workspace_inspect',
  effect: 'LOCAL',
  description: 'Inspect workspace structure, files, and symbols',
  async execute(ctx: AgentContext): Promise<CapabilityResult> {
    try {
      const files = listWorkspaceFiles(ctx.workspacePath);
      const stats = {
        totalFiles: files.length,
        totalLines: 0,
        languages: new Map<string, number>(),
      };
      for (const f of files.slice(0, 50)) {
        try {
          const content = fs.readFileSync(f, 'utf8');
          const lines = content.split('\n').length;
          stats.totalLines += lines;
          const ext = path.extname(f);
          stats.languages.set(ext, (stats.languages.get(ext) || 0) + 1);
        } catch { /* skip unreadable */ }
      }
      const data = {
        workspace: ctx.workspacePath,
        files: files.slice(0, 100),
        stats: {
          totalFiles: stats.totalFiles,
          totalLines: stats.totalLines,
          languages: Object.fromEntries(stats.languages),
        },
      };
      return { success: true, data: JSON.stringify(data, null, 2) };
    } catch (e: any) {
      return { success: false, error: String(e?.message || e) };
    }
  },
};

// ─── symbol_find (LOCAL) ─────────────────────────────────────────────────────

export const symbolFind: Capability = {
  name: 'symbol_find',
  effect: 'LOCAL',
  description: 'Find symbols (functions, classes, variables) in workspace',
  async execute(ctx: AgentContext): Promise<CapabilityResult> {
    try {
      const symbols = findSymbols(ctx.workspacePath, ctx.instruction);
      return { success: true, data: JSON.stringify(symbols, null, 2) };
    } catch (e: any) {
      return { success: false, error: String(e?.message || e) };
    }
  },
};

// ─── symbol_references (LOCAL) ───────────────────────────────────────────────

export const symbolReferences: Capability = {
  name: 'symbol_references',
  effect: 'LOCAL',
  description: 'Find references to a symbol across the workspace',
  async execute(ctx: AgentContext): Promise<CapabilityResult> {
    try {
      const refs = findReferences(ctx.workspacePath, ctx.instruction);
      return { success: true, data: JSON.stringify(refs, null, 2) };
    } catch (e: any) {
      return { success: false, error: String(e?.message || e) };
    }
  },
};

// ─── diagnostics_read (LOCAL) ────────────────────────────────────────────────

export const diagnosticsRead: Capability = {
  name: 'diagnostics_read',
  effect: 'LOCAL',
  description: 'Read VS Code diagnostics (errors, warnings) for workspace',
  async execute(ctx: AgentContext): Promise<CapabilityResult> {
    try {
      const allDiagnostics = vscode.languages.getDiagnostics();
      const diagnostics: Array<{ file: string; severity: string; message: string; line: number }> = [];
      for (const [uri, diags] of allDiagnostics) {
        if (!uri.fsPath.startsWith(ctx.workspacePath)) continue;
        for (const d of diags) {
          diagnostics.push({
            file: uri.fsPath,
            severity: vscode.DiagnosticSeverity[d.severity],
            message: d.message,
            line: d.range.start.line + 1,
          });
        }
      }
      return { success: true, data: JSON.stringify(diagnostics, null, 2) };
    } catch (e: any) {
      return { success: false, error: String(e?.message || e) };
    }
  },
};

// ─── build_run (DURABLE) ─────────────────────────────────────────────────────

export const buildRun: Capability = {
  name: 'build_run',
  effect: 'DURABLE',
  description: 'Run build command (npm run build, tsc, etc.)',
  async execute(ctx: AgentContext): Promise<CapabilityResult> {
    try {
      const { execSync } = require('child_process');
      const pkgPath = path.join(ctx.workspacePath, 'package.json');
      let buildCmd = 'npm run build';
      if (fs.existsSync(pkgPath)) {
        const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
        if (pkg.scripts?.build) buildCmd = 'npm run build';
        else if (pkg.scripts?.compile) buildCmd = 'npm run compile';
      }
      const output = execSync(buildCmd, {
        cwd: ctx.workspacePath,
        encoding: 'utf8',
        timeout: 60000,
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      return { success: true, data: output.slice(0, 4000) };
    } catch (e: any) {
      const output = (e.stdout || '') + (e.stderr || '');
      return { success: false, error: String(e?.message || e), data: output.slice(0, 4000) };
    }
  },
};

// ─── test_run (DURABLE) ──────────────────────────────────────────────────────

export const testRun: Capability = {
  name: 'test_run',
  effect: 'DURABLE',
  description: 'Run test suite (npm test, pytest, etc.)',
  async execute(ctx: AgentContext): Promise<CapabilityResult> {
    try {
      const { execSync } = require('child_process');
      const pkgPath = path.join(ctx.workspacePath, 'package.json');
      let testCmd = 'npm test';
      if (fs.existsSync(pkgPath)) {
        const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
        if (pkg.scripts?.test) testCmd = 'npm test';
      }
      const output = execSync(testCmd, {
        cwd: ctx.workspacePath,
        encoding: 'utf8',
        timeout: 120000,
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      return { success: true, data: output.slice(0, 4000) };
    } catch (e: any) {
      const output = (e.stdout || '') + (e.stderr || '');
      return { success: false, error: String(e?.message || e), data: output.slice(0, 4000) };
    }
  },
};

// ─── git_diff (LOCAL) ────────────────────────────────────────────────────────

export const gitDiff: Capability = {
  name: 'git_diff',
  effect: 'LOCAL',
  description: 'Show git diff (unstaged + staged changes)',
  async execute(ctx: AgentContext): Promise<CapabilityResult> {
    try {
      const { execSync } = require('child_process');
      const diff = execSync('git diff HEAD', {
        cwd: ctx.workspacePath,
        encoding: 'utf8',
        timeout: 30000,
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      return { success: true, data: diff.slice(0, 8000) };
    } catch (e: any) {
      const output = (e.stdout || '') + (e.stderr || '');
      return { success: false, error: String(e?.message || e), data: output.slice(0, 4000) };
    }
  },
};

// ─── receipt_verify (LOCAL) ──────────────────────────────────────────────────

export const receiptVerify: Capability = {
  name: 'receipt_verify',
  effect: 'LOCAL',
  description: 'Verify the receipt hash chain integrity',
  async execute(ctx: AgentContext): Promise<CapabilityResult> {
    try {
      const chain = ctx.receiptChain;
      const valid = chain.verify();
      const receipts = chain.getReceipts();
      return {
        success: true,
        data: JSON.stringify({
          valid,
          totalReceipts: receipts.length,
          lastHash: chain.getLastHash(),
          receipts: receipts.map((r: any) => ({
            index: r.index,
            capability: r.capability,
            state: r.state,
            effect: r.effect,
            hash: r.hash,
            prevHash: r.prevHash,
          })),
        }, null, 2),
      };
    } catch (e: any) {
      return { success: false, error: String(e?.message || e) };
    }
  },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function listWorkspaceFiles(root: string): string[] {
  const results: string[] = [];
  const skip = new Set(['node_modules', '.git', 'out', 'dist', 'build', '.vscode', '__pycache__', '.venv']);
  function walk(dir: string) {
    let entries: fs.Dirent[];
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
    for (const e of entries) {
      if (skip.has(e.name)) continue;
      const full = path.join(dir, e.name);
      if (e.isDirectory()) walk(full);
      else if (e.isFile()) results.push(full);
    }
  }
  walk(root);
  return results;
}

function findSymbols(root: string, query: string): Array<{ name: string; file: string; line: number; kind: string }> {
  const symbols: Array<{ name: string; file: string; line: number; kind: string }> = [];
  const terms = query.toLowerCase().split(/\s+/).filter(t => t.length > 2);
  const files = listWorkspaceFiles(root).filter(f => /\.(ts|js|py|rs|go|java|c|cpp|h)$/.test(f));
  for (const f of files.slice(0, 100)) {
    try {
      const content = fs.readFileSync(f, 'utf8');
      const lines = content.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].toLowerCase();
        for (const term of terms) {
          if (line.includes(term)) {
            symbols.push({ name: lines[i].trim().slice(0, 120), file: f, line: i + 1, kind: 'match' });
            break;
          }
        }
      }
    } catch { /* skip */ }
  }
  return symbols.slice(0, 50);
}

function findReferences(root: string, symbol: string): Array<{ file: string; line: number; text: string }> {
  const refs: Array<{ file: string; line: number; text: string }> = [];
  const files = listWorkspaceFiles(root).filter(f => /\.(ts|js|py|rs|go|java|c|cpp|h)$/.test(f));
  for (const f of files.slice(0, 100)) {
    try {
      const content = fs.readFileSync(f, 'utf8');
      const lines = content.split('\n');
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(symbol)) {
          refs.push({ file: f, line: i + 1, text: lines[i].trim().slice(0, 120) });
        }
      }
    } catch { /* skip */ }
  }
  return refs.slice(0, 50);
}

// ─── Capability Registry ─────────────────────────────────────────────────────

export const CAPABILITIES: Capability[] = [
  workspaceInspect,
  symbolFind,
  symbolReferences,
  diagnosticsRead,
  buildRun,
  testRun,
  gitDiff,
  receiptVerify,
];

export function getCapability(name: string): Capability | undefined {
  return CAPABILITIES.find(c => c.name === name);
}
