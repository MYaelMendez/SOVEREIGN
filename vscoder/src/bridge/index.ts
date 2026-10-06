/**
 * VSCODER:// Bridge — Unified Entry Point
 *
 * Re-exports all public APIs from the 6 bridge modules:
 *   - ipc.ts: JSON-RPC 2.0 IPC server (localhost-only, session auth)
 *   - state.ts: IDE state observer (VSCODER_IDE_STATE_V1, monotonic deltas)
 *   - resolver.ts: Command resolver (LOCAL/DURABLE/EXTERNAL classification)
 *   - plan.ts: Plan validity contract (409 PLAN_STATE_CONFLICT)
 *   - capabilities.ts: Typed IDE capabilities surface (11 namespaces)
 *   - events.ts: Event stream (compact deltas, snapshots, resync)
 *
 * Usage:
 *   import { IpcServer, IDEStateObserver, resolve, PlanBuilder, ... } from './bridge';
 */

// ---------------------------------------------------------------------------
// IPC Module — JSON-RPC 2.0 Server
// ---------------------------------------------------------------------------
export {
  IpcServer,
  MAX_PAYLOAD_SIZE,
  DEFAULT_HOST,
  DEFAULT_PORT,
  SESSION_TTL_MS,
  JSONRPC_VERSION,
  JSON_RPC_PARSE_ERROR,
  JSON_RPC_INVALID_REQUEST,
  JSON_RPC_METHOD_NOT_FOUND,
  JSON_RPC_INVALID_PARAMS,
  JSON_RPC_INTERNAL_ERROR,
  JSON_RPC_SERVER_ERROR,
  JSON_RPC_UNAUTHORIZED,
  JSON_RPC_SESSION_EXPIRED,
  JSON_RPC_SESSION_REVOKED,
  JSON_RPC_PAYLOAD_TOO_LARGE,
} from "./ipc";
export type {
  JsonRpcRequest,
  JsonRpcNotification,
  JsonRpcSuccessResponse,
  JsonRpcErrorResponse,
  JsonRpcError,
  JsonRpcMessage,
  Session,
  HandlerContext,
  MethodHandler,
  IpcServerOptions,
  Logger,
} from "./ipc";

// ---------------------------------------------------------------------------
// Events Module — Event Stream
// ---------------------------------------------------------------------------
export {
  EventStream,
  sanitize,
  sanitizeEvent,
  hashDelta,
  verifyDeltaChain,
} from "./events";
export type {
  DeltaKind,
  DeltaEvent,
  TextChange,
  SelectionInfo,
  DiagnosticSummary,
  SnapshotEvent,
  DocumentSnapshot,
  EditorSnapshot,
  ResyncRequest,
  ResyncResponse,
} from "./events";

// ---------------------------------------------------------------------------
// Plan Module — Plan Validity Contract
// ---------------------------------------------------------------------------
export {
  PlanStateConflictError,
  PlanBuilder,
  PlanValidator,
  buildCurrentState,
  computeWorkspaceHash,
  canonicalJson,
  sha256,
  sha256Buffer,
} from "./plan";
export type {
  Hash,
  RelevantFile,
  ExpectedState,
  Plan,
  CurrentState,
  ValidationResult,
  PlanStateConflict,
  ConflictKind,
} from "./plan";

// ---------------------------------------------------------------------------
// Resolver Module — Command Resolver
// ---------------------------------------------------------------------------
export {
  resolve,
  resolveAll,
  isKnownCommand,
  isKnownEntrypoint,
  getKnownCommands,
  getKnownEntrypoints,
  getCapability,
  resolver,
} from "./resolver";
export type {
  Entrypoint,
  Effect,
  Capability,
  Resolution,
} from "./resolver";

// ---------------------------------------------------------------------------
// Capabilities Module — Typed IDE Capabilities Surface
// ---------------------------------------------------------------------------
export {
  CapabilityRegistry,
  CommandResolver,
  capabilityRegistry,
  commandResolver,
  workspace,
  editor,
  symbol,
  refactor,
  diagnostics,
  task,
  test,
  debug,
  terminal,
  scm,
  ide,
} from "./capabilities";
export type {
  EffectClass,
  LocationInfo,
  SymbolInfo,
  WorkspaceSymbolInfo,
  DiagnosticInfo,
  RefactorActionSummary,
  GitStatusInfo,
  DebugInspectionResult,
  CapabilityDefinition,
  SymbolFindResult,
  SymbolReferencesResult,
  SymbolRenameResult,
  WorkspaceSymbolsResult,
  DiagnosticsReadResult,
  RefactorListResult,
  RefactorApplyResult,
} from "./capabilities";
export { RiskLevel } from "./capabilities";

// ---------------------------------------------------------------------------
// State Module — IDE State Observer
// ---------------------------------------------------------------------------
export {
  IDEStateObserver,
  SNAPSHOT_VERSION,
  IDE_STATE_VERSION,
} from "./state";
export type {
  PlanInvalidation,
  ConfigChange,
  SCMState,
  DebugState,
  TaskState,
  TestState,
  IDEStateSnapshot,
  StateSnapshot,
  IDEDeltaEvent,
  ExtendedDeltaKind,
  PlanInvalidationHandler,
  DeltaHandler,
  SnapshotHandler,
} from "./state";
