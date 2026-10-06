/**
 * VSCODER:// Receipt System — witness.ts
 *
 * Self-contained PC:// receipt model with hash-chain integrity.
 * Each receipt captures:
 *   - intentHash   : SHA-256 of the normalised intent (what the agent was asked to do)
 *   - planHash     : SHA-256 of the plan (steps, approach, tool routing)
 *   - beforeHash   : SHA-256 of the workspace/system state before execution
 *   - afterHash    : SHA-256 of the workspace/system state after execution
 *   - tests        : { passed: number; failed: number; skipped: number; details: TestResult[] }
 *   - previousReceiptHash : SHA-256 of the preceding receipt in the chain ("" for genesis)
 *   - receiptHash  : SHA-256 of all the above fields, canonicalised
 *
 * The receipt contains NO secrets: no file contents, no credentials, no tokens,
 * no environment variables, no absolute paths that leak PII.
 */

import { createHash } from "crypto";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TestResult {
  name: string;
  status: "passed" | "failed" | "skipped";
  durationMs: number;
  message?: string;
}

export interface Receipt {
  intentHash: string;
  planHash: string;
  beforeHash: string;
  afterHash: string;
  tests: {
    passed: number;
    failed: number;
    skipped: number;
    details: TestResult[];
  };
  previousReceiptHash: string;
  receiptHash: string;
}

export interface ReceiptInput {
  intent: string | object;
  plan: string | object;
  before: string | object;
  after: string | object;
  tests?: TestResult[];
}

export interface VerificationResult {
  valid: boolean;
  errors: string[];
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** SHA-256 of an arbitrary value (stringified + canonical JSON). */
function sha256(value: unknown): string {
  const canonical = typeof value === "string" ? value : canonicalJson(value);
  return createHash("sha256").update(canonical, "utf8").digest("hex");
}

/** Deterministic JSON serialisation (sorted keys). */
function canonicalJson(value: unknown): string {
  if (value === null || value === undefined) {
    return "null";
  }
  if (typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return "[" + value.map(canonicalJson).join(",") + "]";
  }
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  const pairs = keys.map(
    (k) => JSON.stringify(k) + ":" + canonicalJson(obj[k])
  );
  return "{" + pairs.join(",") + "}";
}

/** Validate that a hex string is a valid SHA-256 digest. */
function isSha256Hex(s: unknown): s is string {
  return typeof s === "string" && /^[a-f0-9]{64}$/.test(s);
}

/** Validate a TestResult entry (must be secret-free). */
function isValidTestResult(t: unknown): t is TestResult {
  if (typeof t !== "object" || t === null) return false;
  const tr = t as Record<string, unknown>;
  return (
    typeof tr.name === "string" &&
    tr.name.length > 0 &&
    (tr.status === "passed" || tr.status === "failed" || tr.status === "skipped") &&
    typeof tr.durationMs === "number" &&
    tr.durationMs >= 0 &&
    (tr.message === undefined || typeof tr.message === "string")
  );
}

// ---------------------------------------------------------------------------
// receipt.generate
// ---------------------------------------------------------------------------

/**
 * Generate a new receipt and append it to the hash chain.
 *
 * @param input   Receipt data (intent, plan, before, after, tests).
 * @param previousReceiptHash  Hash of the previous receipt ("" for genesis).
 * @returns       A fully-hashed Receipt object.
 */
export function generate(input: ReceiptInput, previousReceiptHash = ""): Receipt {
  const intentHash = sha256(input.intent);
  const planHash = sha256(input.plan);
  const beforeHash = sha256(input.before);
  const afterHash = sha256(input.after);

  const testDetails = (input.tests ?? []).filter(isValidTestResult);
  const passed = testDetails.filter((t) => t.status === "passed").length;
  const failed = testDetails.filter((t) => t.status === "failed").length;
  const skipped = testDetails.filter((t) => t.status === "skipped").length;

  const receipt: Receipt = {
    intentHash,
    planHash,
    beforeHash,
    afterHash,
    tests: { passed, failed, skipped, details: testDetails },
    previousReceiptHash,
    receiptHash: "", // placeholder — computed below
  };

  // receiptHash is computed over all fields except receiptHash itself.
  const { receiptHash: _omit, ...payload } = receipt;
  receipt.receiptHash = sha256(payload);

  return receipt;
}

// ---------------------------------------------------------------------------
// receipt.verify
// ---------------------------------------------------------------------------

/**
 * Verify a single receipt's internal integrity.
 * Checks:
 *   1. All hash fields are valid SHA-256 hex strings.
 *   2. tests.details are well-formed.
 *   3. The receiptHash matches the recomputed hash of all other fields.
 *
 * Note: This does NOT validate the chain linkage — use verifyChain() for that.
 */
export function verify(receipt: unknown): VerificationResult {
  const errors: string[] = [];

  if (typeof receipt !== "object" || receipt === null) {
    return { valid: false, errors: ["Receipt is not an object"] };
  }

  const r = receipt as Record<string, unknown>;

  // 1. Hash field format
  const hashFields = [
    "intentHash",
    "planHash",
    "beforeHash",
    "afterHash",
    "previousReceiptHash",
    "receiptHash",
  ];
  for (const field of hashFields) {
    if (!isSha256Hex(r[field])) {
      errors.push(`Field '${field}' is not a valid SHA-256 hex string`);
    }
  }

  // 2. Tests structure
  const tests = r.tests;
  if (typeof tests !== "object" || tests === null) {
    errors.push("Field 'tests' is not an object");
  } else {
    const t = tests as Record<string, unknown>;
    if (
      typeof t.passed !== "number" ||
      typeof t.failed !== "number" ||
      typeof t.skipped !== "number"
    ) {
      errors.push("Test counts (passed/failed/skipped) must be numbers");
    }
    if (!Array.isArray(t.details)) {
      errors.push("Field 'tests.details' must be an array");
    } else {
      for (let i = 0; i < t.details.length; i++) {
        if (!isValidTestResult(t.details[i])) {
          errors.push(`tests.details[${i}] is malformed`);
        }
      }
    }
  }

  // 3. Recompute receiptHash
  if (errors.length === 0) {
    const { receiptHash: _omit, ...payload } = r as unknown as Receipt;
    const expected = sha256(payload);
    if (expected !== r.receiptHash) {
      errors.push(
        `receiptHash mismatch: expected ${expected}, got ${r.receiptHash}`
      );
    }
  }

  return { valid: errors.length === 0, errors };
}

// ---------------------------------------------------------------------------
// receipt.chain (verifyChain)
// ---------------------------------------------------------------------------

/**
 * Verify an ordered chain of receipts.
 * Checks:
 *   1. Each receipt passes verify().
 *   2. Each receipt's previousReceiptHash matches the prior receipt's receiptHash.
 *   3. The first receipt has previousReceiptHash === "" (genesis).
 */
export function verifyChain(receipts: unknown[]): VerificationResult {
  const errors: string[] = [];

  if (!Array.isArray(receipts)) {
    return { valid: false, errors: ["Input is not an array"] };
  }

  for (let i = 0; i < receipts.length; i++) {
    const receipt = receipts[i];
    const single = verify(receipt);
    if (!single.valid) {
      errors.push(`Receipt[${i}]: ${single.errors.join("; ")}`);
      continue;
    }

    const r = receipt as Receipt;

    if (i === 0) {
      if (r.previousReceiptHash !== "") {
        errors.push(
          `Receipt[0]: genesis receipt must have previousReceiptHash === ""`
        );
      }
    } else {
      const prev = receipts[i - 1] as Receipt;
      if (r.previousReceiptHash !== prev.receiptHash) {
        errors.push(
          `Receipt[${i}]: previousReceiptHash mismatch — expected ${prev.receiptHash}, got ${r.previousReceiptHash}`
        );
      }
    }
  }

  return { valid: errors.length === 0, errors };
}

// ---------------------------------------------------------------------------
// Receipt chain builder (class-based convenience)
// ---------------------------------------------------------------------------

export class ReceiptChain {
  private receipts: Receipt[] = [];

  /** Add a new receipt to the chain. */
  append(input: ReceiptInput): Receipt {
    const prevHash =
      this.receipts.length > 0
        ? this.receipts[this.receipts.length - 1].receiptHash
        : "";
    const receipt = generate(input, prevHash);
    this.receipts.push(receipt);
    return receipt;
  }

  /** Verify the entire chain. */
  verify(): VerificationResult {
    return verifyChain(this.receipts);
  }

  /** Get all receipts in order. */
  getReceipts(): readonly Receipt[] {
    return this.receipts;
  }

  /** Get the latest receipt (or null if empty). */
  getLatest(): Receipt | null {
    return this.receipts.length > 0
      ? this.receipts[this.receipts.length - 1]
      : null;
  }

  /** Replace the entire chain (e.g. after loading from disk). */
  replaceAll(receipts: Receipt[]): void {
    this.receipts = [...receipts];
  }
}
