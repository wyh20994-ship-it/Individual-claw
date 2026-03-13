"""
SetContextTool — 让 LLM 主动写入 work_memory
LLM 可以在多步骤任务中调用此工具保存/更新任意状态键值，
下一轮对话时这些状态会出现在 system prompt 的"工作上下文"中。
"""

from __future__ import annotations
from typing import Any

from agent.tools.base import BaseTool, ToolParameter
from utils.logger import logger


class SetContextTool(BaseTool):
    name = "set_context"
    description = (
        "保存当前任务的状态信息（如步骤、订单ID、中间数据等），"
        "供后续对话使用。例如多步骤任务中记录当前进行到哪一步。"
    )
    parameters = [
        ToolParameter(
            name="key",
            type="string",
            description="状态键名，如 'step'、'order_id'、'selected_item'",
        ),
        ToolParameter(
            name="value",
            type="string",
            description="状态值（字符串）",
        ),
        ToolParameter(
            name="ttl",
            type="string",
            description="有效期（秒），默认 300 秒（5分钟）",
            required=False,
        ),
    ]

    def __init__(self, work_memory):
        self.work_memory = work_memory

    async def execute(
        self,
        key: str = "",
        value: str = "",
        ttl: str = "300",
        user_id: str = "unknown",   # 由 AgentCore._process_response 注入，不暴露给 LLM
        **kwargs: Any,
    ) -> str:
        if not key:
            return "错误: key 不能为空"

        try:
            ttl_int = int(ttl)
        except (ValueError, TypeError):
            ttl_int = 300

        # 读取当前状态后合并写入，避免覆盖同一用户其他 key
        current: dict = self.work_memory.get(user_id) or {}
        current[key] = value
        self.work_memory.set(user_id, current, ttl=ttl_int)

        logger.debug(f"[SetContext] {user_id}: {key}={value} (ttl={ttl_int}s)")
        return f"已保存: {key} = {value}"
