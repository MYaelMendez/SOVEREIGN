/**
 * VSCODER:// Authority Policy Module
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
  /** Unique operation name, e.g. "fs.read", "git.commit", "http.fetch" */
  name: string;
  /** Target resource URI, e.g. "file:///path", "https://api.example.com" */
  target: string;
  /** Arbitrary operation parameters */
  params?: Record<string, unknown>;
  /** Optional human-readable description for confirmation prompts */
  description?: string;
}

export interface Assessment {
  risk: RiskLevel;
  /** Human-readable explanation of the risk classification */
  reason: string;
  /** Whether a grant is required before execution */
  grantRequired: boolean;
  /** Whether a passkey is required (EXTERNAL only) */
  passkeyRequired: boolean;
  /** Whether user confirmation is required (DURABLE and EXTERNAL) */
  confirmationRequired: boolean;
}

export interface Grant {
  /** Opaque grant token (base64url) */
  token: string;
  /** SHA-256 hash of the canonical operation this grant is bound to */
  operationHash: string;
  /** Epoch milliseconds when this grant expires */
  expiresAt: number;
  /** Passkey identifier used to sign (EXTERNAL grants only) */
  passkeyId?: string;
  /** HMAC-SHA256 signature over operationHash + expiresAt */
  signature: string;
}

export interface CredentialReference {
  /** Vault key or URI identifying the credential */
  ref: string;
  /** Optional vault namespace */
  namespace?: string;
}

export interface ResolvedCredential {
  ref: string;
  /** Resolved secret value (handled carefully – never log) */
  value: string;
  /** Epoch ms when this resolution expires */
  expiresAt: number;
}

export interface CapabilityInvocation {
  capability: string;
  grant: Grant;
  params?: Record<string, unknown>;
}

export interface InvocationResult {
  success: boolean;
  capability: string;
  output?: unknown;
  error?: string;
}

// ---------------------------------------------------------------------------
// Policy Engine
// ---------------------------------------------------------------------------

/**
 * Classify an operation into a risk level.
 *
 * Rules:
 *   - Targets using file://, memory://, or no scheme → LOCAL
 *   - Targets using git://, fs:// (write), or durable:// → DURABLE
 *   - Targets using http://, https://, tcp://, dns://, or any other remote scheme → EXTERNAL
 */
export function assess(operation: Operation): Assessment {
  const { name, target } = operation;

  // Explicit local schemes
  if (
    target.startsWith("file://") ||
    target.startsWith("memory://") ||
    target.startsWith("local://") ||
    target.startsWith("vscoder://")
  ) {
    // Even file:// writes are DURABLE if the operation is a write
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

  // Durable schemes
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

  // External schemes (default for anything else)
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

  // Unknown scheme – treat as EXTERNAL for safety
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

const GRANT_TTL_MS = 5 * 60 * 1000; // 5 minutes
const HMAC_SECRET = getHmacSecret();

/**
 * Request a grant for an operation.
 *
 * For LOCAL operations, returns a no-op grant (no signature needed).
 * For DURABLE operations, returns a signed grant bound to the operation hash.
 * For EXTERNAL operations, requires a passkeyId and returns a signed grant.
 */
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
      signature: "", // No signature needed for LOCAL
    };
  }

  if (assessment.risk === "EXTERNAL") {
    if (!options?.passkeyId) {
      throw new Error(
        `EXTERNAL operation '${operation.name}' requires a passkeyId`
      );
    }
    const signature = signGrant(operationHash, expiresAt, options.passkeyId);
    return {
      token: encodeToken({
        op: operationHash,
        exp: expiresAt,
        lvl: "EXTERNAL",
        pid: options.passkeyId,
      }),
      operationHash,
      expiresAt,
      passkeyId: options.passkeyId,
      signature,
    };
  }

  // DURABLE
  const signature = signGrant(operationHash, expiresAt, "durable");
  return {
    token: encodeToken({ op: operationHash, exp: expiresAt, lvl: "DURABLE" }),
    operationHash,
    expiresAt,
    signature,
  };
}

/**
 * Verify a grant is valid: not expired, correctly signed, and bound to the
 * expected operation.
 */
export function verifyGrant(
  grant: Grant,
  expectedOperation: Operation
): boolean {
  // Check expiry
  if (Date.now() > grant.expiresAt) {
    return false;
  }

  // Check operation binding
  const expectedHash = hashOperation(expectedOperation);
  if (grant.operationHash !== expectedHash) {
    return false;
  }

  // LOCAL grants have no signature
  if (grant.signature === "") {
    return true;
  }

  // Verify HMAC signature
  const passkeyId = grant.passkeyId ?? "durable";
  const expectedSig = signGrant(
    grant.operationHash,
    grant.expiresAt,
    passkeyId
  );
  return crypto.timingSafeEqual(
    Buffer.from(grant.signature, "hex"),
    Buffer.from(expectedSig, "hex")
  );
}

// ---------------------------------------------------------------------------
// Vault: Credential Resolution
// ---------------------------------------------------------------------------

/**
 * In-memory credential store. In production this would interface with
 * the OS keychain, 1Password, Bitwarden, or Hermes vault.
 */
const credentialStore = new Map<string, string>();

/**
 * Register a credential in the vault (for testing/demo purposes).
 */
export function vaultStore(ref: string, value: string): void {
  credentialStore.set(ref, value);
}

/**
 * Resolve a credential reference to its secret value.
 *
 * Supports:
 *   - vault://<ref>  – look up in the local credential store
 *   - env://<name>   – read from process environment
 *   - ref as-is     – treat as a literal value (for testing)
 */
export function resolveCredential(ref: CredentialReference): ResolvedCredential {
  const { ref: rawRef, namespace } = ref;
  const fullRef = namespace ? `${namespace}:${rawRef}` : rawRef;

  // vault:// scheme
  if (rawRef.startsWith("vault://")) {
    const key = rawRef.slice("vault://".length);
    const value = credentialStore.get(key);
    if (value === undefined) {
      throw new Error(`Credential not found in vault: ${key}`);
    }
    return {
      ref: fullRef,
      value,
      expiresAt: Date.now() + 60_000, // 1 minute resolution TTL
    };
  }

  // env:// scheme
  if (rawRef.startsWith("env://")) {
    const envName = rawRef.slice("env://".length);
    const value = process.env[envName];
    if (value === undefined) {
      throw new Error(`Environment variable not found: ${envName}`);
    }
    return {
      ref: fullRef,
      value,
      expiresAt: Date.now() + 60_000,
    };
  }

  // Literal value (testing only – never do this in production)
  return {
    ref: fullRef,
    value: rawRef,
    expiresAt: Date.now() + 60_000,
  };
}

// ---------------------------------------------------------------------------
// Vault: Capability Invocation
// ---------------------------------------------------------------------------

/**
 * Invoke a capability with a valid grant.
 *
 * The grant is verified against the operation before the capability is
 * executed. The capability receives the resolved parameters and returns
 * a result.
 */
export function invokeCapability(
  invocation: CapabilityInvocation
): InvocationResult {
  const { capability, grant, params } = invocation;

  // Reconstruct a minimal operation for verification
  const operation: Operation = {
    name: capability,
    target: params?.target as string ?? "unknown://",
    params,
  };

  if (!verifyGrant(grant, operation)) {
    return {
      success: false,
      capability,
      error: "Grant verification failed – expired, tampered, or wrong operation",
    };
  }

  // Dispatch to capability handler
  try {
    const output = dispatchCapability(capability, params);
    return { success: true, capability, output };
  } catch (err) {
    return {
      success: false,
      capability,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

// ---------------------------------------------------------------------------
// Internal Helpers
// ---------------------------------------------------------------------------

function isWriteOperation(name: string): boolean {
  const writePrefixes = [
    "fs.write",
    "fs.delete",
    "fs.rename",
    "fs.mkdir",
    "fs.chmod",
    "git.commit",
    "git.push",
    "git.merge",
    "git.reset",
    "db.insert",
    "db.update",
    "db.delete",
    "durable.write",
    "durable.update",
    "durable.delete",
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

function signGrant(
  operationHash: string,
  expiresAt: number,
  passkeyId: string
): string {
  const payload = `${operationHash}:${expiresAt}:${passkeyId}`;
  return crypto.createHmac("sha256", HMAC_SECRET).update(payload).digest("hex");
}

function encodeToken(payload: Record<string, unknown>): string {
  const json = JSON.stringify(payload);
  return Buffer.from(json).toString("base64url");
}

function getHmacSecret(): string {
  // In production this would come from a secure enclave or keychain.
  // For this module we derive a stable secret from the machine.
  const machineId = crypto
    .createHash("sha256")
    .update(process.platform + process.arch + process.pid)
    .digest("hex")
    .slice(0, 32);
  return machineId;
}

function dispatchCapability(
  capability: string,
  params?: Record<string, unknown>
): unknown {
  // This is a stub dispatcher. In production, capabilities would be
  // registered by extensions and dispatched via a registry.
  const handlers: Record<string, (p?: Record<string, unknown>) => unknown> = {
    "http.fetch": (p) => ({
      status: 200,
      url: p?.url,
      body: `Fetched ${p?.url}`,
    }),
    "git.commit": (p) => ({
      committed: true,
      message: p?.message,
      hash: crypto.randomBytes(4).toString("hex"),
    }),
    "fs.read": (p) => ({
      content: `Content of ${p?.path}`,
      path: p?.path,
    }),
    "fs.write": (p) => ({
      written: true,
      path: p?.path,
      bytes: String(p?.content ?? "").length,
    }),
  };

  const handler = handlers[capability];
  if (!handler) {
    throw new Error(`Unknown capability: ${capability}`);
  }
  return handler(params);
}

// ---------------------------------------------------------------------------
// Re-exports for convenience
// ---------------------------------------------------------------------------

export const policy = { assess };
export const grant = { request: requestGrant, verify: verifyGrant };
export const vault = {
  resolve: resolveCredential,
  invoke: invokeCapability,
  store: vaultStore,
};
