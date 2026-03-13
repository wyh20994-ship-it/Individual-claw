/**
 * JSON-RPC 2.0 类型定义与工具函数
 */

export interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: string;
  method: string;
  params: Record<string, unknown>;
}

export interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: string;
  result?: unknown;
  error?: JsonRpcError;
}

export interface JsonRpcError {
  code: number;
  message: string;
  data?: unknown;
}

export function createRpcResponse(id: string, result: unknown): JsonRpcResponse {
  return { jsonrpc: "2.0", id, result };
}

export function createRpcError(id: string, code: number, message: string, data?: unknown): JsonRpcResponse {
  return { jsonrpc: "2.0", id, error: { code, message, data } };
}
