/**
 * VSCODER://BRIDGE — Authority Policy Module
 *
 * PC:// authority model:
 *   LOCAL    – no grant needed (read-only, in-memory, ephemeral)
 *   DURABLE  – policy/confirmation required (persistent state changes)
 *   EXTERNAL – passkey + transaction-bound grant required (network, APIs)
 *
 * Self-contained: uses only Node.js built-ins (crypto). No external deps.
 */

import * as crypto from "crypto";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RiskLevel = "LOCAL" | "DURABLE" | "EXTERNAL";

export interface Operation {
  name: string;
  target: string;
  params?: Record<string, unknown>;
  description?: string;
}

export interface Assessment {
  risk: RiskLevel;
  reason: string;
  grantRequired: boolean;
  passkeyRequired: boolean;
  confirmationRequired: boolean;
}

export interface Grant {
  token: string;
  operationHash: string;
  expiresAt: number;
  passkeyId?: string;
  signature: string;
}

// ---------------------------------------------------------------------------
// Policy Engine
// ---------------------------------------------------------------------------

export function assess(operation: Operation): Assessment {
  const { name, target } = operation;

  if (
    target.startsWith("file://") ||
    target.startsWith("memory://") ||
    target.startsWith("local://") ||
    target.startsWith("vscoder://")
  ) {
    if (isWriteOperation(name)) {
      return {
        risk: "DURABLE",
        reason: `Write operation '${name}' on local target '${target}'`,
        grantRequired: true,
        passkeyRequired: false,
        confirmationRequired: true,
      };
    }
    return {
      risk: "LOCAL",
      reason: `Read-only operation '${name}' on local target '${target}'`,
      grantRequired: false,
      passkeyRequired: false,
      confirmationRequired: false,
    };
  }

  if (
    target.startsWith("git://") ||
    target.startsWith("durable://") ||
    target.startsWith("fs://") ||
    target.startsWith("db://")
  ) {
    return {
      risk: "DURABLE",
      reason: `Operation '${name}' on durable target '${target}'`,
      grantRequired: true,
      passkeyRequired: false,
      confirmationRequired: true,
    };
  }

  if (
    target.startsWith("http://") ||
    target.startsWith("https://") ||
    target.startsWith("tcp://") ||
    target.startsWith("udp://") ||
    target.startsWith("dns://") ||
    target.startsWith("smtp://") ||
    target.startsWith("ftp://") ||
    target.startsWith("ssh://") ||
    target.startsWith("api://")
  ) {
    return {
      risk: "EXTERNAL",
      reason: `Operation '${name}' on external target '${target}'`,
      grantRequired: true,
      passkeyRequired: true,
      confirmationRequired: true,
    };
  }

  return {
    risk: "EXTERNAL",
    reason: `Unknown scheme in target '${target}' – defaulting to EXTERNAL`,
    grantRequired: true,
    passkeyRequired: true,
    confirmationRequired: true,
  };
}

// ---------------------------------------------------------------------------
// Grant Management
// ---------------------------------------------------------------------------

const GRANT_TTL_MS = 5 * 60 * 1000;
const HMAC_SECRET = getHmacSecret();

export function requestGrant(
  operation: Operation,
  options?: { passkeyId?: string; ttlMs?: number }
): Grant {
  const assessment = assess(operation);
  const operationHash = hashOperation(operation);
  const ttl = options?.ttlMs ?? GRANT_TTL_MS;
  const expiresAt = Date.now() + ttl;

  if (assessment.risk === "LOCAL") {
    return {
      token: encodeToken({ op: operationHash, exp: expiresAt, lvl: "LOCAL" }),
      operationHash,
      expiresAt,
      signature: "",
    };
  }

  if (assessment.risk === "EXTERNAL") {
    if (!options?.passkeyId) {
      throw new Error(`EXTERNAL operation '${operation.name}' requires a passkeyId`);
    }
    const signature = signGrant(operationHash, expiresAt, options.passkeyId);
    return {
      token: encodeToken({ op: operationHash, exp: expiresAt, lvl: "EXTERNAL", pid: options.passkeyId }),
      operationHash,
      expiresAt,
      passkeyId: options.passkeyId,
      signature,
    };
  }

  const signature = signGrant(operationHash, expiresAt, "durable");
  return {
    token: encodeToken({ op: operationHash, exp: expiresAt, lvl: "DURABLE" }),
    operationHash,
    expiresAt,
    signature,
  };
}

export function verifyGrant(grant: Grant, expectedOperation: Operation): boolean {
  if (Date.now() > grant.expiresAt) return false;
  const expectedHash = hashOperation(expectedOperation);
  if (grant.operationHash !== expectedHash) return false;
  if (grant.signature === "") return true;
  const passkeyId = grant.passkeyId ?? "durable";
  const expectedSig = signGrant(grant.operationHash, grant.expiresAt, passkeyId);
  return crypto.timingSafeEqual(
    Buffer.from(grant.signature, "hex"),
    Buffer.from(expectedSig, "hex")
  );
}

// ---------------------------------------------------------------------------
// Internal Helpers
// ---------------------------------------------------------------------------

function isWriteOperation(name: string): boolean {
  const writePrefixes = [
    "fs.write", "fs.delete", "fs.rename", "fs.mkdir", "fs.chmod",
    "git.commit", "git.push", "git.merge", "git.reset",
    "db.insert", "db.update", "db.delete",
    "durable.write", "durable.update", "durable.delete",
  ];
  return writePrefixes.some(
    (prefix) => name.startsWith(prefix) || name === prefix
  );
}

function hashOperation(operation: Operation): string {
  const canonical = JSON.stringify({
    name: operation.name,
    target: operation.target,
    params: operation.params ?? {},
  });
  return crypto.createHash("sha256").update(canonical).digest("hex");
}

function signGrant(operationHash: string, expiresAt: number, passkeyId: string): string {
  const payload = `${operationHash}:${expiresAt}:${passkeyId}`;
  return crypto.createHmac("sha256", HMAC_SECRET).update(payload).digest("hex");
}

function encodeToken(payload: Record<string, unknown>): string {
  const json = JSON.stringify(payload);
  return Buffer.from(json).toString("base64url");
}

function getHmacSecret(): string {
  const machineId = crypto
    .createHash("sha256")
    .update(process.platform + process.arch + process.pid)
    .digest("hex")
    .slice(0, 32);
  return machineId;
}

export const policy = { assess };
export const grant = { request: requestGrant, verify: verifyGrant };
