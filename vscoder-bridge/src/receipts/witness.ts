/**
 * VSCODER://BRIDGE — Receipt System with SHA-256 Hash Chain
 *
 * Each receipt captures:
 *   - intentHash   : SHA-256 of the normalised intent
 *   - planHash     : SHA-256 of the plan
 *   - beforeHash   : SHA-256 of the workspace state before execution
 *   - afterHash    : SHA-256 of the workspace state after execution
 *   - tests        : { passed, number; failed: number; skipped: number; details: TestResult[] }
 *   - previousReceiptHash : SHA-256 of the preceding receipt in the chain ("" for genesis)
 *   - receiptHash  : SHA-256 of all the above fields, canonicalised
 *
 * The receipt contains NO secrets: no file contents, no credentials, no tokens.
 */

import { createHash } from "crypto";

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

function sha256(value: unknown): string {
  const canonical = typeof value === "string" ? value : canonicalJson(value);
  return createHash("sha256").update(canonical, "utf8").digest("hex");
}

function canonicalJson(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value !== "object") return JSON.stringify(value);
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

function isSha256Hex(s: unknown): s is string {
  return typeof s === "string" && /^[a-f0-9]{64}$/.test(s);
}

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
    receiptHash: "",
  };

  const { receiptHash: _omit, ...payload } = receipt;
  receipt.receiptHash = sha256(payload);

  return receipt;
}

export function verify(receipt: unknown): VerificationResult {
  const errors: string[] = [];

  if (typeof receipt !== "object" || receipt === null) {
    return { valid: false, errors: ["Receipt is not an object"] };
  }

  const r = receipt as Record<string, unknown>;

  const hashFields = [
    "intentHash", "planHash", "beforeHash", "afterHash",
    "previousReceiptHash", "receiptHash",
  ];
  for (const field of hashFields) {
    if (!isSha256Hex(r[field])) {
      errors.push(`Field '${field}' is not a valid SHA-256 hex string`);
    }
  }

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

  if (errors.length === 0) {
    const { receiptHash: _omit, ...payload } = r as unknown as Receipt;
    const expected = sha256(payload);
    if (expected !== r.receiptHash) {
      errors.push(`receiptHash mismatch: expected ${expected}, got ${r.receiptHash}`);
    }
  }

  return { valid: errors.length === 0, errors };
}

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
        errors.push(`Receipt[0]: genesis receipt must have previousReceiptHash === ""`);
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

export class ReceiptChain {
  private receipts: Receipt[] = [];

  append(input: ReceiptInput): Receipt {
    const prevHash =
      this.receipts.length > 0
        ? this.receipts[this.receipts.length - 1].receiptHash
        : "";
    const receipt = generate(input, prevHash);
    this.receipts.push(receipt);
    return receipt;
  }

  verify(): VerificationResult {
    return verifyChain(this.receipts);
  }

  getReceipts(): readonly Receipt[] {
    return this.receipts;
  }

  getLatest(): Receipt | null {
    return this.receipts.length > 0
      ? this.receipts[this.receipts.length - 1]
      : null;
  }

  replaceAll(receipts: Receipt[]): void {
    this.receipts = [...receipts];
  }
}
