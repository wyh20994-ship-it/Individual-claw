import { WebSocketServer, WebSocket } from "ws";
import { v4 as uuidv4 } from "uuid";
import { logger } from "./utils/logger";
import { JsonRpcRequest, JsonRpcResponse, createRpcResponse, createRpcError } from "./rpc/json-rpc";

let rpcClients: Map<string, WebSocket> = new Map();

/**
 * 启动 WebSocket JSON-RPC Server，供 Python Runner 连接
 */
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
    });
  });
}

/**
 * 向 Runner 发送 JSON-RPC 请求
 */
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

// 回调注册表（简化版，生产中应用 Promise / EventEmitter）
const pendingCallbacks = new Map<string, (result: unknown) => void>();

export function onRpcResult(id: string, cb: (result: unknown) => void) {
  pendingCallbacks.set(id, cb);
}

function handleRunnerResponse(_clientId: string, msg: JsonRpcResponse) {
  if (msg.id && pendingCallbacks.has(msg.id)) {
    const cb = pendingCallbacks.get(msg.id)!;
    pendingCallbacks.delete(msg.id);
    cb(msg.result ?? msg.error);
  }
}
