"""
JSON-RPC 方法调度器
将 Gateway 发来的 RPC 请求路由到 AgentCore 对应方法
"""

from __future__ import annotations
from typing import Any

from utils.logger import logger


async def dispatch(request: dict, agent) -> dict:
    """
    处理 JSON-RPC 2.0 请求，返回响应
    """
    rpc_id = request.get("id", "0")
    method = request.get("method", "")
    params = request.get("params", {})

    try:
        if method == "agent.chat":
            user_id = params.get("userId", "unknown")
            content = params.get("content", "")
            result = await agent.chat(user_id, content, **params)
            return _ok(rpc_id, {"reply": result})

        elif method == "agent.clear_memory":
            user_id = params.get("userId", "unknown")
            agent.conv_memory.clear(user_id)
            return _ok(rpc_id, {"cleared": True})

        elif method == "ping":
            return _ok(rpc_id, "pong")

        else:
            return _error(rpc_id, -32601, f"Method not found: {method}")

    except Exception as e:
        logger.error(f"[RPC] dispatch error: {e}")
        return _error(rpc_id, -32000, str(e))


def _ok(rpc_id: str, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _error(rpc_id: str, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}
