import { WebSocketServer, WebSocket } from "ws";
import { v4 as uuidv4 } from "uuid";
import { logger } from "../utils/logger";
import { JsonRpcRequest, JsonRpcResponse } from "./json-rpc";

const rpcClients = new Map<string, WebSocket>();
const pendingCallbacks = new Map<
  string,
  {
    resolve: (result: unknown) => void;
    reject: (err: Error) => void;
    timer: NodeJS.Timeout;
  }
>();

export async function startRpcServer(port: number): Promise<void> {
  const wss = new WebSocketServer({ port });

  wss.on("connection", (ws: WebSocket) => {
    const clientId = uuidv4();
    rpcClients.set(clientId, ws);
    logger.info(`[RPC] Runner connected: ${clientId}`);

    ws.on("message", (raw: Buffer) => {
      try {
        const msg: JsonRpcResponse = JSON.parse(raw.toString());
        handleRunnerResponse(clientId, msg);
      } catch (err) {
        logger.error(`[RPC] Invalid message from ${clientId}`, err);
      }
    });

    ws.on("close", () => {
      rpcClients.delete(clientId);
      logger.info(`[RPC] Runner disconnected: ${clientId}`);
      rejectAllPending("Runner disconnected");
    });

    ws.on("error", (err) => {
      logger.error(`[RPC] Runner socket error: ${clientId}`, err);
    });
  });
}

export function sendToRunner(method: string, params: Record<string, unknown>): string | null {
  const client = rpcClients.values().next().value as WebSocket | undefined;
  if (!client || client.readyState !== WebSocket.OPEN) {
    logger.warn("[RPC] No runner connected");
    return null;
  }

  const id = uuidv4();
  const request: JsonRpcRequest = { jsonrpc: "2.0", id, method, params };
  client.send(JSON.stringify(request));
  return id;
}

export async function sendToRunnerAndWait(
  method: string,
  params: Record<string, unknown>,
  timeoutMs = 20_000,
): Promise<unknown> {
  const id = sendToRunner(method, params);
  if (!id) {
    throw new Error("Runner not connected");
  }

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pendingCallbacks.delete(id);
      reject(new Error(`Runner response timeout after ${timeoutMs}ms`));
    }, timeoutMs);

    pendingCallbacks.set(id, { resolve, reject, timer });
  });
}

function handleRunnerResponse(_clientId: string, msg: JsonRpcResponse) {
  if (!msg.id || !pendingCallbacks.has(msg.id)) {
    return;
  }

  const pending = pendingCallbacks.get(msg.id)!;
  pendingCallbacks.delete(msg.id);
  clearTimeout(pending.timer);

  if (msg.error) {
    pending.reject(new Error(msg.error.message));
    return;
  }

  pending.resolve(msg.result);
}

function rejectAllPending(message: string) {
  for (const [id, pending] of pendingCallbacks.entries()) {
    clearTimeout(pending.timer);
    pending.reject(new Error(message));
    pendingCallbacks.delete(id);
  }
}
