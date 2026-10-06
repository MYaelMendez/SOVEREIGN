/**
 * VSCODER:// IPC/RPC Server — bridge/ipc.ts
 *
 * Phase 2: JSON-RPC 2.0 over TCP (localhost-only) with session authentication,
 * message schema validation, 64KB payload cap, concurrent request handling,
 * and clean shutdown.
 *
 * Security invariants:
 *   - Localhost-only: binds exclusively to 127.0.0.1.
 *   - Connection possession ≠ authority: a TCP connection grants nothing.
 *     Authority is granted per-session via token authentication and can be
 *     revoked at any time without closing the connection.
 *   - Every message is validated against the JSON-RPC 2.0 schema.
 *   - Every message after auth must reference a valid, non-revoked session.
 *   - Payloads are capped at 64KB; oversized messages are rejected and the
 *     connection is closed.
 *
 * Self-contained: uses only Node.js built-ins (net, crypto). No external deps.
 */

import * as net from "net";
import { randomBytes, timingSafeEqual } from "crypto";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Maximum payload size in bytes (64 KB). */
export const MAX_PAYLOAD_SIZE = 64 * 1024;

/** Default listen host — localhost only. */
export const DEFAULT_HOST = "127.0.0.1";

/** Default listen port (0 = ephemeral). */
export const DEFAULT_PORT = 0;

/** Session TTL in milliseconds (30 minutes). */
export const SESSION_TTL_MS = 30 * 60 * 1000;

/** JSON-RPC 2.0 version string. */
export const JSONRPC_VERSION = "2.0" as const;

// ---------------------------------------------------------------------------
// JSON-RPC 2.0 Types
// ---------------------------------------------------------------------------

/** JSON-RPC 2.0 request object. */
export interface JsonRpcRequest {
  jsonrpc: "2.0";
  method: string;
  params?: Record<string, unknown>;
  id: string | number | null;
}

/** JSON-RPC 2.0 notification (no id). */
export interface JsonRpcNotification {
  jsonrpc: "2.0";
  method: string;
  params?: Record<string, unknown>;
}

/** JSON-RPC 2.0 success response. */
export interface JsonRpcSuccessResponse {
  jsonrpc: "2.0";
  result: unknown;
  id: string | number | null;
}

/** JSON-RPC 2.0 error response. */
export interface JsonRpcErrorResponse {
  jsonrpc: "2.0";
  error: JsonRpcError;
  id: string | number | null;
}

/** JSON-RPC 2.0 error object. */
export interface JsonRpcError {
  code: number;
  message: string;
  data?: unknown;
}

/** Union of all JSON-RPC message types. */
export type JsonRpcMessage =
  | JsonRpcRequest
  | JsonRpcNotification
  | JsonRpcSuccessResponse
  | JsonRpcErrorResponse;

// ---------------------------------------------------------------------------
// JSON-RPC 2.0 Error Codes
// ---------------------------------------------------------------------------

export const JSON_RPC_PARSE_ERROR = -32700;
export const JSON_RPC_INVALID_REQUEST = -32600;
export const JSON_RPC_METHOD_NOT_FOUND = -32601;
export const JSON_RPC_INVALID_PARAMS = -32602;
export const JSON_RPC_INTERNAL_ERROR = -32603;
export const JSON_RPC_SERVER_ERROR = -32000;
export const JSON_RPC_UNAUTHORIZED = -32001;
export const JSON_RPC_SESSION_EXPIRED = -32002;
export const JSON_RPC_SESSION_REVOKED = -32003;
export const JSON_RPC_PAYLOAD_TOO_LARGE = -32004;

// ---------------------------------------------------------------------------
// Session Types
// ---------------------------------------------------------------------------

/** An authenticated session. */
export interface Session {
  /** Unique session ID. */
  id: string;
  /** The connection this session is bound to. */
  connectionId: string;
  /** When the session was created (epoch ms). */
  createdAt: number;
  /** When the session expires (epoch ms). */
  expiresAt: number;
  /** Whether the session has been revoked. */
  revoked: boolean;
}

// ---------------------------------------------------------------------------
// Handler Types
// ---------------------------------------------------------------------------

/** Context passed to method handlers. */
export interface HandlerContext {
  /** The authenticated session. */
  session: Session;
  /** The raw params from the request. */
  params: any;
  /** The connection ID. */
  connectionId: string;
}

/** A JSON-RPC method handler. */
export type MethodHandler = (
  context: HandlerContext
) => Promise<unknown> | unknown;

// ---------------------------------------------------------------------------
// IPC Server Options
// ---------------------------------------------------------------------------

/** Options for creating an IPC server. */
export interface IpcServerOptions {
  /** Host to bind to. Defaults to 127.0.0.1. */
  host?: string;
  /** Port to bind to. Defaults to 0 (ephemeral). */
  port?: number;
  /** Authentication token(s). Clients must present one of these. */
  tokens: string[];
  /** Session TTL in milliseconds. Defaults to 30 minutes. */
  sessionTtlMs?: number;
  /** Custom logger. Defaults to console. */
  logger?: Logger;
}

/** Simple logger interface. */
export interface Logger {
  info(message: string, ...args: unknown[]): void;
  warn(message: string, ...args: unknown[]): void;
  error(message: string, ...args: unknown[]): void;
}

// ---------------------------------------------------------------------------
// Connection State
// ---------------------------------------------------------------------------

/** Per-connection state. */
interface ConnectionState {
  id: string;
  socket: net.Socket;
  buffer: Buffer;
  session: Session | null;
  closed: boolean;
}

// ---------------------------------------------------------------------------
// IPC Server
// ---------------------------------------------------------------------------

/**
 * VSCODER:// IPC/RPC Server.
 *
 * JSON-RPC 2.0 over TCP with localhost-only binding, session authentication,
 * message validation, payload size limits, concurrent request handling,
 * and clean shutdown.
 */
export class IpcServer {
  private server: net.Server | null = null;
  private options: Required<IpcServerOptions>;
  private connections: Map<string, ConnectionState> = new Map();
  private sessions: Map<string, Session> = new Map();
  private handlers: Map<string, MethodHandler> = new Map();
  private pendingRequests: Map<string, number> = new Map();
  private connectionCounter = 0;
  private shuttingDown = false;
  private shutdownPromise: Promise<void> | null = null;
  private shutdownResolve: (() => void) | null = null;

  /**
   * Methods that do not require authentication.
   * Only auth.authenticate is public by default.
   */
  private static readonly PUBLIC_METHODS = new Set(["auth.authenticate"]);

  constructor(options: IpcServerOptions) {
    if (!options.tokens || options.tokens.length === 0) {
      throw new Error("At least one authentication token is required");
    }

    this.options = {
      host: options.host ?? DEFAULT_HOST,
      port: options.port ?? DEFAULT_PORT,
      tokens: options.tokens,
      sessionTtlMs: options.sessionTtlMs ?? SESSION_TTL_MS,
      logger: options.logger ?? console,
    };

    // Enforce localhost-only binding
    if (this.options.host !== "127.0.0.1" && this.options.host !== "::1") {
      throw new Error(
        `IPC server must bind to localhost only. Got: ${this.options.host}`
      );
    }

    // Register built-in handlers (auth.authenticate is handled specially)
    this.registerHandler("auth.revoke", this.handleAuthRevoke.bind(this));
    this.registerHandler("auth.session", this.handleAuthSession.bind(this));
  }

  /**
   * Register a handler for a JSON-RPC method.
   */
  registerHandler(method: string, handler: MethodHandler): void {
    this.handlers.set(method, handler);
  }

  /**
   * Start the IPC server.
   */
  async start(): Promise<{ host: string; port: number }> {
    if (this.server) {
      throw new Error("Server is already running");
    }

    this.server = net.createServer((socket) => {
      this.handleConnection(socket);
    });

    this.server.on("error", (err) => {
      this.options.logger.error("IPC server error:", err);
    });

    await new Promise<void>((resolve, reject) => {
      this.server!.listen(this.options.port, this.options.host, () => {
        resolve();
      });
      this.server!.once("error", reject);
    });

    const address = this.server.address();
    if (!address || typeof address !== "object") {
      throw new Error("Failed to get server address");
    }

    this.options.logger.info(
      `IPC server listening on ${address.address}:${address.port}`
    );

    return { host: address.address, port: address.port };
  }

  /**
   * Gracefully shut down the IPC server.
   *
   * Stops accepting new connections, waits for pending requests to complete,
   * then closes all connections.
   */
  async shutdown(timeoutMs = 5000): Promise<void> {
    if (this.shuttingDown) {
      return this.shutdownPromise ?? Promise.resolve();
    }

    this.shuttingDown = true;
    this.shutdownPromise = new Promise<void>((resolve) => {
      this.shutdownResolve = resolve;
    });

    this.options.logger.info("IPC server shutting down...");

    // Stop accepting new connections
    if (this.server) {
      this.server.close(() => {
        this.options.logger.info("IPC server stopped accepting connections");
      });
    }

    // Close all connections
    for (const [id, conn] of this.connections) {
      this.options.logger.info(`Closing connection ${id}`);
      conn.closed = true;
      conn.socket.destroy();
    }
    this.connections.clear();

    // Clear all sessions
    this.sessions.clear();

    // Wait for pending requests (with timeout)
    const startTime = Date.now();
    while (this.pendingRequests.size > 0) {
      if (Date.now() - startTime > timeoutMs) {
        this.options.logger.warn(
          `Shutdown timeout reached with ${this.pendingRequests.size} pending requests`
        );
        break;
      }
      await new Promise((r) => setTimeout(r, 50));
    }

    this.options.logger.info("IPC server shut down complete");
    this.shutdownResolve?.();
    return this.shutdownPromise;
  }

  /**
   * Get the number of active connections.
   */
  getConnectionCount(): number {
    return this.connections.size;
  }

  /**
   * Get the number of active sessions.
   */
  getSessionCount(): number {
    return this.sessions.size;
  }

  /**
   * Get the number of pending requests.
   */
  getPendingRequestCount(): number {
    return this.pendingRequests.size;
  }

  // -------------------------------------------------------------------------
  // Connection Handling
  // -------------------------------------------------------------------------

  private handleConnection(socket: net.Socket): void {
    if (this.shuttingDown) {
      socket.destroy();
      return;
    }

    const connectionId = `conn-${++this.connectionCounter}`;
    const state: ConnectionState = {
      id: connectionId,
      socket,
      buffer: Buffer.alloc(0),
      session: null,
      closed: false,
    };

    this.connections.set(connectionId, state);
    this.options.logger.info(`New connection: ${connectionId}`);

    socket.on("data", (data: Buffer) => {
      if (state.closed) return;

      // Check payload size before appending
      if (state.buffer.length + data.length > MAX_PAYLOAD_SIZE) {
        this.options.logger.warn(
          `Payload too large from ${connectionId}: ${state.buffer.length + data.length} bytes`
        );
        this.sendError(
          state,
          null,
          JSON_RPC_PAYLOAD_TOO_LARGE,
          `Payload exceeds maximum size of ${MAX_PAYLOAD_SIZE} bytes`
        );
        this.closeConnection(state);
        return;
      }

      state.buffer = Buffer.concat([state.buffer, data]);

      // Process complete messages (newline-delimited)
      let newlineIndex: number;
      while ((newlineIndex = state.buffer.indexOf(0x0a)) !== -1) {
        const line = state.buffer.slice(0, newlineIndex);
        state.buffer = state.buffer.slice(newlineIndex + 1);

        if (line.length === 0) {
          continue; // skip empty lines
        }

        // Check individual message size
        if (line.length > MAX_PAYLOAD_SIZE) {
          this.options.logger.warn(
            `Message too large from ${connectionId}: ${line.length} bytes`
          );
          this.sendError(
            state,
            null,
            JSON_RPC_PAYLOAD_TOO_LARGE,
            `Message exceeds maximum size of ${MAX_PAYLOAD_SIZE} bytes`
          );
          this.closeConnection(state);
          return;
        }

        // Process message asynchronously
        this.processMessage(state, line.toString("utf8")).catch((err) => {
          this.options.logger.error(
            `Error processing message on ${connectionId}:`,
            err
          );
        });
      }
    });

    socket.on("close", () => {
      this.cleanupConnection(state);
    });

    socket.on("error", (err) => {
      this.options.logger.error(`Connection error ${connectionId}:`, err);
      this.cleanupConnection(state);
    });
  }

  private cleanupConnection(state: ConnectionState): void {
    if (state.closed) return;
    state.closed = true;
    this.connections.delete(state.id);
    if (state.session) {
      this.sessions.delete(state.session.id);
    }
    this.options.logger.info(`Connection closed: ${state.id}`);
  }

  private closeConnection(state: ConnectionState): void {
    state.closed = true;
    state.socket.destroy();
    this.cleanupConnection(state);
  }

  // -------------------------------------------------------------------------
  // Message Processing
  // -------------------------------------------------------------------------

  private async processMessage(
    state: ConnectionState,
    rawMessage: string
  ): Promise<void> {
    if (state.closed) return;

    // Parse JSON
    let message: any;
    try {
      message = JSON.parse(rawMessage);
    } catch {
      this.sendError(state, null, JSON_RPC_PARSE_ERROR, "Invalid JSON");
      return;
    }

    // Validate JSON-RPC 2.0 schema
    const validationError = this.validateJsonRpcSchema(message);
    if (validationError) {
      this.sendError(state, null, JSON_RPC_INVALID_REQUEST, validationError);
      return;
    }

    // Ignore responses from clients
    if (this.isResponse(message)) {
      this.options.logger.warn("Received response from client — ignoring");
      return;
    }

    const request = message as JsonRpcRequest | JsonRpcNotification;
    const requestId = "id" in request ? request.id : null;

    // Check if method is public
    const isPublic = IpcServer.PUBLIC_METHODS.has(request.method);

    // Non-public methods require a valid session
    if (!isPublic) {
      if (!state.session) {
        this.sendError(
          state,
          requestId,
          JSON_RPC_UNAUTHORIZED,
          "Authentication required"
        );
        return;
      }

      // Validate session
      const sessionError = this.validateSession(state.session);
      if (sessionError) {
        this.sendError(state, requestId, sessionError.code, sessionError.message);
        return;
      }
    }

    // Special handling for auth.authenticate
    if (request.method === "auth.authenticate") {
      await this.handleAuthAuthenticateRequest(state, request);
      return;
    }

    // Route to handler
    const handler = this.handlers.get(request.method);
    if (!handler) {
      this.sendError(
        state,
        requestId,
        JSON_RPC_METHOD_NOT_FOUND,
        `Method not found: ${request.method}`
      );
      return;
    }

    // Track pending request
    const pendingKey = `${state.id}:${requestId ?? `notif-${Date.now()}`}`;
    this.pendingRequests.set(pendingKey, Date.now());

    try {
      const params = request.params ?? {};
      const context: HandlerContext = {
        session: state.session!,
        params,
        connectionId: state.id,
      };

      const result = await handler(context);

      // Send success response (only for requests, not notifications)
      if (requestId !== null) {
        this.sendResult(state, requestId, result);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.sendError(state, requestId, JSON_RPC_INTERNAL_ERROR, message);
    } finally {
      this.pendingRequests.delete(pendingKey);
    }
  }

  // -------------------------------------------------------------------------
  // Schema Validation
  // -------------------------------------------------------------------------

  private validateJsonRpcSchema(message: unknown): string | null {
    if (typeof message !== "object" || message === null) {
      return "Message must be an object";
    }

    const msg = message as Record<string, unknown>;

    // Check jsonrpc version
    if (msg.jsonrpc !== JSONRPC_VERSION) {
      return `jsonrpc must be "${JSONRPC_VERSION}"`;
    }

    // Check method (required for requests and notifications)
    if (typeof msg.method !== "string" || msg.method.length === 0) {
      return "method must be a non-empty string";
    }

    // Check params (optional, but must be object if present)
    if (msg.params !== undefined) {
      if (
        typeof msg.params !== "object" ||
        msg.params === null ||
        Array.isArray(msg.params)
      ) {
        return "params must be an object";
      }
    }

    // Check id (required for requests, absent for notifications)
    if ("id" in msg) {
      const id = msg.id;
      if (id !== null && typeof id !== "string" && typeof id !== "number") {
        return "id must be a string, number, or null";
      }
    }

    // Check result/error (for responses)
    if ("result" in msg && "error" in msg) {
      return "response cannot have both result and error";
    }
    if (!("result" in msg) && !("error" in msg)) {
      return "response must have either result or error";
    }

    return null;
  }

  private isResponse(message: unknown): boolean {
    if (typeof message !== "object" || message === null) return false;
    const msg = message as Record<string, unknown>;
    return "result" in msg || "error" in msg;
  }

  // -------------------------------------------------------------------------
  // Session Management
  // -------------------------------------------------------------------------

  private validateSession(
    session: Session
  ): { code: number; message: string } | null {
    if (session.revoked) {
      return {
        code: JSON_RPC_SESSION_REVOKED,
        message: "Session has been revoked",
      };
    }
    if (Date.now() > session.expiresAt) {
      return {
        code: JSON_RPC_SESSION_EXPIRED,
        message: "Session has expired",
      };
    }
    return null;
  }

  private createSession(connectionId: string): Session {
    const session: Session = {
      id: randomBytes(16).toString("hex"),
      connectionId,
      createdAt: Date.now(),
      expiresAt: Date.now() + this.options.sessionTtlMs,
      revoked: false,
    };
    this.sessions.set(session.id, session);
    return session;
  }

  // -------------------------------------------------------------------------
  // Built-in Handlers
  // -------------------------------------------------------------------------

  private async handleAuthAuthenticateRequest(
    state: ConnectionState,
    request: JsonRpcRequest | JsonRpcNotification
  ): Promise<void> {
    const requestId = "id" in request ? request.id : null;
    const params = request.params ?? {};

    const token = params.token;
    if (typeof token !== "string" || token.length === 0) {
      this.sendError(
        state,
        requestId,
        JSON_RPC_INVALID_PARAMS,
        "token is required"
      );
      return;
    }

    if (!this.validateToken(token)) {
      this.sendError(
        state,
        requestId,
        JSON_RPC_UNAUTHORIZED,
        "Invalid authentication token"
      );
      return;
    }

    // Revoke existing session if any
    if (state.session) {
      state.session.revoked = true;
      this.sessions.delete(state.session.id);
    }

    // Create new session
    const session = this.createSession(state.id);
    state.session = session;

    this.options.logger.info(
      `Session ${session.id} authenticated on ${state.id}`
    );

    if (requestId !== null) {
      this.sendResult(state, requestId, {
        sessionId: session.id,
        createdAt: session.createdAt,
        expiresAt: session.expiresAt,
      });
    }
  }

  private async handleAuthRevoke(context: HandlerContext): Promise<unknown> {
    const session = this.sessions.get(context.session.id);
    if (session) {
      session.revoked = true;
      this.sessions.delete(session.id);
    }

    // Also clear from connection state
    const conn = this.connections.get(context.connectionId);
    if (conn && conn.session?.id === context.session.id) {
      conn.session = null;
    }

    return { revoked: true };
  }

  private async handleAuthSession(context: HandlerContext): Promise<unknown> {
    const session = context.session;
    return {
      sessionId: session.id,
      createdAt: session.createdAt,
      expiresAt: session.expiresAt,
      revoked: session.revoked,
    };
  }

  // -------------------------------------------------------------------------
  // Token Validation
  // -------------------------------------------------------------------------

  private validateToken(token: string): boolean {
    const tokenBuffer = Buffer.from(token, "utf8");
    for (const validToken of this.options.tokens) {
      const validBuffer = Buffer.from(validToken, "utf8");
      if (
        tokenBuffer.length === validBuffer.length &&
        timingSafeEqual(tokenBuffer, validBuffer)
      ) {
        return true;
      }
    }
    return false;
  }

  // -------------------------------------------------------------------------
  // Response Sending
  // -------------------------------------------------------------------------

  private sendResult(
    state: ConnectionState,
    id: string | number | null,
    result: unknown
  ): void {
    if (state.closed) return;
    const response: JsonRpcSuccessResponse = {
      jsonrpc: JSONRPC_VERSION,
      result,
      id,
    };
    this.sendRaw(state, response);
  }

  private sendError(
    state: ConnectionState,
    id: string | number | null,
    code: number,
    message: string,
    data?: unknown
  ): void {
    if (state.closed) return;
    const response: JsonRpcErrorResponse = {
      jsonrpc: JSONRPC_VERSION,
      error: { code, message, ...(data !== undefined && { data }) },
      id,
    };
    this.sendRaw(state, response);
  }

  private sendRaw(state: ConnectionState, message: JsonRpcMessage): void {
    if (state.closed) return;
    try {
      const json = JSON.stringify(message) + "\n";
      state.socket.write(json);
    } catch (err) {
      this.options.logger.error(
        `Failed to send message on ${state.id}:`,
        err
      );
    }
  }
}
