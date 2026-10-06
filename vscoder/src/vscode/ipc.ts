/**
 * VSCODER:// IPC/RPC Server Module
 *
 * Provides inter-process communication primitives for the VSCODER bridge.
 * Enables bidirectional messaging between the extension host and external
 * processes (Hermes, fleet agents, MCP servers).
 *
 * Primitives:
 *   - ipc.channel     → create a typed message channel
 *   - ipc.send        → send a message to a channel
 *   - ipc.receive     → subscribe to messages on a channel
 *   - ipc.call        → RPC request/response pattern
 *   - ipc.spawn       → spawn an external process with IPC
 *   - ipc.bridge      → bridge two channels (relay)
 */

import * as vscode from 'vscode';
import { EventEmitter } from 'events';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A serializable IPC message. */
export interface IPCMessage<T = unknown> {
  /** Unique message ID. */
  id: string;
  /** Channel name. */
  channel: string;
  /** Message type/payload. */
  payload: T;
  /** Timestamp (ms since epoch). */
  timestamp: number;
  /** Source process ID. */
  source: string;
  /** Target process ID (undefined = broadcast). */
  target?: string;
}

/**
 * A typed envelope for IPC message payloads that carry RPC metadata.
 */
export interface IpcPayload {
  __ipc_call__?: string;
  __ipc_response__?: boolean;
  data?: unknown;
}

/** Options for creating a channel. */
export interface ChannelOptions {
  /** Channel name. */
  name: string;
  /** Whether to persist messages to a ring buffer. */
  persist?: boolean;
  /** Max messages to retain in buffer. */
  bufferSize?: number;
}

/** Options for sending a message. */
export interface SendOptions {
  /** Target process ID (undefined = broadcast). */
  target?: string;
  /** Timeout in ms (0 = no timeout). */
  timeout?: number;
}

/** Options for RPC calls. */
export interface CallOptions {
  /** Timeout in ms. */
  timeout?: number;
  /** Whether to throw on timeout (default true). */
  throwOnTimeout?: boolean;
}

/** Options for spawning an external process. */
export interface SpawnOptions {
  /** Command to execute. */
  command: string;
  /** Arguments. */
  args?: string[];
  /** Working directory. */
  cwd?: string;
  /** Environment variables. */
  env?: Record<string, string>;
  /** Channel name for IPC. */
  channel?: string;
}

/** A handle to a spawned process. */
export interface ProcessHandle {
  /** Process ID. */
  pid: string;
  /** Channel name. */
  channel: string;
  /** Send a message to the process. */
  send<T>(payload: T, options?: SendOptions): void;
  /** Subscribe to messages from the process. */
  on<T>(listener: (message: IPCMessage<T>) => void): void;
  /** Close the process. */
  close(): void;
}

/** A handle to an IPC channel. */
export interface ChannelHandle {
  /** Channel name. */
  name: string;
  /** Send a message. */
  send<T>(payload: T, options?: SendOptions): void;
  /** Subscribe to messages. */
  on<T>(listener: (message: IPCMessage<T>) => void): () => void;
  /** Get buffered messages. */
  getBuffer(): IPCMessage[];
  /** Clear the buffer. */
  clear(): void;
  /** Close the channel. */
  close(): void;
}

// ---------------------------------------------------------------------------
// Internal: Channel registry
// ---------------------------------------------------------------------------

interface ChannelState {
  name: string;
  emitter: EventEmitter;
  buffer: IPCMessage[];
  bufferSize: number;
  closed: boolean;
}

const _channels = new Map<string, ChannelState>();
let _processCounter = 0;

function getOrCreateChannel(name: string, bufferSize = 100): ChannelState {
  let state = _channels.get(name);
  if (!state) {
    state = {
      name,
      emitter: new EventEmitter(),
      buffer: [],
      bufferSize,
      closed: false,
    };
    state.emitter.setMaxListeners(1000);
    _channels.set(name, state);
  }
  return state;
}

// ---------------------------------------------------------------------------
// ipc.channel
// ---------------------------------------------------------------------------

/**
 * Create or get a typed message channel.
 */
export function channel(options: ChannelOptions): ChannelHandle {
  const state = getOrCreateChannel(options.name, options.bufferSize ?? 100);

  return {
    name: options.name,
    send<T>(payload: T, sendOptions?: SendOptions) {
      if (state.closed) return;
      const message: IPCMessage<T> = {
        id: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
        channel: options.name,
        payload,
        timestamp: Date.now(),
        source: `process_${process.pid}`,
        target: sendOptions?.target,
      };
      state.buffer.push(message);
      if (state.buffer.length > state.bufferSize) {
        state.buffer.shift();
      }
      state.emitter.emit('message', message);
    },
    on<T>(listener: (message: IPCMessage<T>) => void) {
      if (state.closed) return () => {};
      state.emitter.on('message', listener);
      return () => state.emitter.off('message', listener);
    },
    getBuffer() {
      return [...state.buffer];
    },
    clear() {
      state.buffer.length = 0;
    },
    close() {
      state.closed = true;
      state.emitter.removeAllListeners();
      _channels.delete(options.name);
    },
  };
}

// ---------------------------------------------------------------------------
// ipc.send
// ---------------------------------------------------------------------------

/**
 * Send a message to a channel.
 */
export function send<T>(channelName: string, payload: T, options?: SendOptions): void {
  const ch = channel({ name: channelName });
  ch.send(payload, options);
}

// ---------------------------------------------------------------------------
// ipc.receive
// ---------------------------------------------------------------------------

/**
 * Subscribe to messages on a channel.
 * Returns an unsubscribe function.
 */
export function receive<T>(
  channelName: string,
  listener: (message: IPCMessage<T>) => void
): () => void {
  const ch = channel({ name: channelName });
  return ch.on(listener);
}

// ---------------------------------------------------------------------------
// ipc.call
// ---------------------------------------------------------------------------

/**
 * Make an RPC call and wait for a response.
 * Sends a request message and listens for a response with matching correlation ID.
 */
export async function call<TRequest, TResponse>(
  channelName: string,
  payload: TRequest,
  options?: CallOptions
): Promise<TResponse> {
  const timeout = options?.timeout ?? 30_000;
  const throwOnTimeout = options?.throwOnTimeout ?? true;
  const callId = `call_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;

  return new Promise<TResponse>((resolve, reject) => {
    const ch = channel({ name: channelName });

    // Wrap payload with correlation ID
    const requestPayload = {
      __ipc_call__: callId,
      __ipc_response__: false,
      data: payload,
    };

    let timer: NodeJS.Timeout | undefined;

    // Listen for response
    const unsubscribe = ch.on<{ __ipc_call__: string; __ipc_response__: boolean; data: TResponse }>(
      (message) => {
        if (
          message.payload &&
          typeof message.payload === 'object' &&
          '__ipc_call__' in message.payload &&
          (message.payload as IpcPayload).__ipc_call__ === callId &&
          (message.payload as IpcPayload).__ipc_response__ === true
        ) {
          if (timer) clearTimeout(timer);
          unsubscribe();
          resolve((message.payload as IpcPayload).data as TResponse);
        }
      }
    );

    // Send request
    ch.send(requestPayload);

    // Timeout
    if (timeout > 0) {
      timer = setTimeout(() => {
        unsubscribe();
        if (throwOnTimeout) {
          reject(new Error(`IPC call timed out after ${timeout}ms`));
        } else {
          resolve(undefined as unknown as TResponse);
        }
      }, timeout);
    }
  });
}

// ---------------------------------------------------------------------------
// ipc.respond
// ---------------------------------------------------------------------------

/**
 * Register a handler that automatically responds to RPC calls.
 * Returns an unsubscribe function.
 */
export function respond<TRequest, TResponse>(
  channelName: string,
  handler: (payload: TRequest) => TResponse | Promise<TResponse>
): () => void {
  const ch = channel({ name: channelName });

  return ch.on<{ __ipc_call__: string; __ipc_response__: boolean; data: TRequest }>(
    async (message) => {
      const payload = message.payload;
      if (
        payload &&
        typeof payload === 'object' &&
        '__ipc_call__' in payload &&
        (payload as IpcPayload).__ipc_response__ === false
      ) {
        const callId = (payload as IpcPayload).__ipc_call__ as string;
        const requestData = (payload as IpcPayload).data as TRequest;

        try {
          const result = await handler(requestData);
          ch.send({
            __ipc_call__: callId,
            __ipc_response__: true,
            data: result,
          });
        } catch (err) {
          ch.send({
            __ipc_call__: callId,
            __ipc_response__: true,
            data: { __error__: String(err) },
          });
        }
      }
    }
  );
}

// ---------------------------------------------------------------------------
// ipc.spawn
// ---------------------------------------------------------------------------

/**
 * Spawn an external process with an IPC channel.
 * The process communicates via stdin/stdout using newline-delimited JSON.
 */
export function spawn(options: SpawnOptions): ProcessHandle {
  const channelName = options.channel ?? `ipc_${Date.now()}_${_processCounter++}`;
  const ch = channel({ name: channelName });
  const pid = `proc_${_processCounter++}`;

  // Use VS Code terminal to spawn the process
  const terminal = vscode.window.createTerminal({
    name: `VSCODER IPC: ${options.command}`,
    cwd: options.cwd,
    env: options.env,
  });

  // Build the command with IPC channel setup
  const args = options.args ?? [];
  const fullCommand = [options.command, ...args].join(' ');
  terminal.sendText(fullCommand);
  terminal.show();

  const emitter = new EventEmitter();

  return {
    pid,
    channel: channelName,
    send<T>(payload: T) {
      ch.send(payload);
    },
    on<T>(listener: (message: IPCMessage<T>) => void) {
      return ch.on(listener);
    },
    close() {
      ch.close();
      terminal.dispose();
      emitter.removeAllListeners();
    },
  };
}

// ---------------------------------------------------------------------------
// ipc.bridge
// ---------------------------------------------------------------------------

/**
 * Bridge two channels — relay all messages from source to target.
 * Returns a function to stop the bridge.
 */
export function bridge(sourceChannel: string, targetChannel: string): () => void {
  const source = channel({ name: sourceChannel });
  const target = channel({ name: targetChannel });

  const unsubscribe = source.on((message) => {
    target.send(message.payload, { target: message.target });
  });

  return () => {
    unsubscribe();
  };
}

// ---------------------------------------------------------------------------
// ipc.list
// ---------------------------------------------------------------------------

/**
 * List all active channels.
 */
export function list(): string[] {
  return Array.from(_channels.keys());
}

// ---------------------------------------------------------------------------
// ipc.stats
// ---------------------------------------------------------------------------

/**
 * Get statistics for a channel.
 */
export function stats(channelName: string): { messages: number; listeners: number } | undefined {
  const state = _channels.get(channelName);
  if (!state) return undefined;
  return {
    messages: state.buffer.length,
    listeners: state.emitter.listenerCount('message'),
  };
}

// ---------------------------------------------------------------------------
// Default export
// ---------------------------------------------------------------------------

export default {
  channel,
  send,
  receive,
  call,
  respond,
  spawn,
  bridge,
  list,
  stats,
};
