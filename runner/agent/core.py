"""
AgentCore — HangClaw 的 Agent 核心执行引擎
负责编排 LLM、Memory、Tools、Skills 完成对话
"""

from __future__ import annotations
from typing import Any

from agent.llm.router import LLMRouter
from agent.memory.conversation import ConversationMemory
from agent.memory.semantic import SemanticMemory
from agent.memory.working import WorkingMemory
from agent.tools import get_all_tools
from agent.tools.context_tool import SetContextTool
from agent.skills.loader import SkillLoader
from utils.logger import logger


class AgentCore:
    """接收用户消息 → 组装 Prompt → 调用 LLM → 解析工具调用 → 返回回复"""

    def __init__(self, config: dict):
        self.config = config
        runner_cfg = config.get("runner", {})

        # LLM 路由
        self.llm = LLMRouter(runner_cfg.get("llm", {}))

        # 三层记忆
        self.conv_memory = ConversationMemory(runner_cfg.get("memory", {}).get("conversation", {}))
        self.sem_memory = SemanticMemory(runner_cfg.get("memory", {}).get("semantic", {}))
        self.work_memory = WorkingMemory(runner_cfg.get("memory", {}).get("working", {}))

        # 工具
        self.tools = get_all_tools(runner_cfg.get("tools", {}))
        # 注入 work_memory 引用，让 LLM 可主动写入任务状态
        self.tools.append(SetContextTool(self.work_memory))

    async def initialize(self):
        """异步初始化（连接外部服务等）"""
        await self.sem_memory.initialize()
        logger.info("[AgentCore] Semantic memory initialized")

    async def chat(self, user_id: str, content: str, **kwargs: Any) -> str:
        """
        主对话入口
        """
        # 1. 读取/更新对话记忆
        history = self.conv_memory.get_history(user_id)

        # 2. 查询语义记忆（RAG）
        relevant = await self.sem_memory.query(content, top_k=3)

        # 3. 查询工作记忆
        context = self.work_memory.get(user_id)

        # 4. 组装 system prompt
        system_prompt = self._build_system_prompt(relevant, context)

        # 5. 构建消息序列
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": content})

        # 6. 调用 LLM（支持工具调用）
        tool_schemas = [t.schema() for t in self.tools]
        response = await self.llm.chat(messages, tools=tool_schemas)

        # 7. 如果 LLM 要求调用工具，则执行
        assistant_content = await self._process_response(response, messages, user_id)

        # 8. 存储对话
        self.conv_memory.add_turn(user_id, "user", content)
        self.conv_memory.add_turn(user_id, "assistant", assistant_content)

        # 9. 异步写入语义记忆
        await self.sem_memory.add(content, metadata={"user_id": user_id, "role": "user"})

        # 10. 本轮未调用工具则清除上轮工具缓存，避免过期上下文干扰下一轮
        if not self.work_memory.get(user_id):
            pass  # 已过期或本轮无工具调用，无需处理
        else:
            # 保留 300s 内的工具结果，到期由 TTL 自动清理
            pass

        return assistant_content

    async def _process_response(self, response: dict, messages: list, user_id: str) -> str:
        """处理 LLM 回复，如有 tool_calls 则循环执行"""
        msg = response.get("message", {})
        tool_calls = msg.get("tool_calls")

        if not tool_calls:
            return msg.get("content", "")

        tool_results: list[dict] = []

        # 执行工具
        for call in tool_calls:
            tool_name = call["function"]["name"]
            tool_args = call["function"]["arguments"]
            tool = self._find_tool(tool_name)
            if tool:
                # 注入 user_id，set_context 等工具需要它来定位 work_memory key
                result = await tool.execute(**tool_args, user_id=user_id)
                tool_results.append({"tool": tool_name, "args": tool_args, "result": str(result)})
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": str(result)})
            else:
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": f"Tool '{tool_name}' not found"})

        # 将本轮所有工具调用结果写入工作记忆，下一轮对话可在 system prompt 中感知
        if tool_results:
            self.work_memory.set(user_id, {"last_tool_calls": tool_results}, ttl=300)
            logger.debug(f"[WorkMemory] Saved {len(tool_results)} tool result(s) for {user_id}")

        # 将工具结果再次交给 LLM
        follow_up = await self.llm.chat(messages)
        return follow_up.get("message", {}).get("content", "")

    def _find_tool(self, name: str):
        for t in self.tools:
            if t.name == name:
                return t
        return None

    def _build_system_prompt(self, relevant_memories: list[str], working_ctx: dict | None) -> str:
        parts = [
            "你是 HangClaw 智能助手，可以使用工具完成用户请求。",
            "请用中文回复。",
        ]
        if relevant_memories:
            parts.append("## 相关记忆\n" + "\n".join(f"- {m}" for m in relevant_memories))
        if working_ctx:
            parts.append(f"## 工作上下文\n{working_ctx}")
        return "\n\n".join(parts)
