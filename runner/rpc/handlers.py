from __future__ import annotations

from typing import Any

from agent.schemas import RpcError, RpcRequest, RpcResponse
from utils.logger import logger


async def dispatch(request: dict, agent) -> dict:
    try:
        rpc_request = RpcRequest.model_validate(request)
    except Exception as e:
        return RpcResponse(id="0", error=RpcError(code=-32600, message=f"Invalid request: {e}")).model_dump(
            exclude_none=True
        )

    rpc_id = rpc_request.id
    method = rpc_request.method
    params = rpc_request.params

    try:
        if method == "agent.chat":
            user_id = str(params.get("userId") or "unknown")
            content = str(params.get("content") or "")
            result = await agent.chat(user_id, content, **params)
            return _ok(rpc_id, {"reply": result})

        if method == "agent.clear_memory":
            user_id = str(params.get("userId") or "unknown")
            agent.conv_memory.clear(user_id)
            agent.work_memory.delete(user_id)
            if hasattr(agent.sem_memory, "delete_user"):
                await agent.sem_memory.delete_user(user_id)
            return _ok(rpc_id, {"cleared": True, "userId": user_id})

        if method == "ping":
            return _ok(rpc_id, "pong")

        return _error(rpc_id, -32601, f"Method not found: {method}")

    except Exception as e:
        logger.exception(f"[RPC] dispatch error: {e}")
        return _error(rpc_id, -32000, str(e))


def _ok(rpc_id: str | int, result: Any) -> dict:
    return RpcResponse(id=rpc_id, result=result).model_dump(exclude_none=True)


def _error(rpc_id: str | int, code: int, message: str) -> dict:
    return RpcResponse(id=rpc_id, error=RpcError(code=code, message=message)).model_dump(exclude_none=True)
