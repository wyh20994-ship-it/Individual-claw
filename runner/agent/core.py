"""
AgentCore — HangClaw 的 Agent 核心执行引擎
负责编排 LLM、Memory、Tools、Skills 完成对话
"""

from __future__ import annotations
import json
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

        # ReAct / Planning 配置
        agent_cfg = runner_cfg.get("agent", {})
        self.max_reasoning_steps = agent_cfg.get("max_reasoning_steps", 6)
        self.tool_result_ttl = agent_cfg.get("tool_result_ttl", 300)

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

        # 6. 调用 LLM（支持多步 ReAct + 工具调用）
        assistant_content = await self._run_react_loop(messages, user_id)

        # 7. 存储对话
        self.conv_memory.add_turn(user_id, "user", content)
        self.conv_memory.add_turn(user_id, "assistant", assistant_content)

        # 8. 异步写入语义记忆
        await self.sem_memory.add(content, metadata={"user_id": user_id, "role": "user"})

        return assistant_content

    async def _run_react_loop(self, messages: list[dict], user_id: str) -> str:
        """以 ReAct 方式循环：规划 → 工具执行 → 观察 → 再规划，直到产出最终答复。"""
        tool_schemas = [t.schema() for t in self.tools]
        final_content = ""

        for step in range(1, self.max_reasoning_steps + 1):
            response = await self.llm.chat(messages, tools=tool_schemas)
            msg = response.get("message", {})
            tool_calls = msg.get("tool_calls") or []
            content = msg.get("content") or ""
            final_content = content or final_content

            assistant_message = self._build_assistant_message(msg)
            messages.append(assistant_message)

            if not tool_calls:
                return content

            tool_results = await self._execute_tool_calls(tool_calls, user_id)
            self._append_tool_messages(messages, tool_calls, tool_results)
            self._save_tool_results(user_id, step, tool_results)

        logger.warning(f"[AgentCore] ReAct loop reached max steps for {user_id}")
        if final_content:
            return final_content
        return f"已达到最大执行步数（{self.max_reasoning_steps}），请将任务拆小后再试。"

    async def _execute_tool_calls(self, tool_calls: list[dict], user_id: str) -> list[dict]:
        """执行本轮所有工具调用。"""
        results: list[dict] = []

        for call in tool_calls:
            tool_name = call["function"]["name"]
            tool_args = self._parse_tool_args(call["function"].get("arguments"))
            tool = self._find_tool(tool_name)

            if not tool:
                results.append(
                    {
                        "tool": tool_name,
                        "args": tool_args,
                        "result": f"Tool '{tool_name}' not found",
                    }
                )
                continue

            try:
                result = await tool.execute(**tool_args, user_id=user_id)
            except Exception as e:
                logger.exception(f"[AgentCore] Tool execution failed: {tool_name}")
                result = f"工具执行失败: {e}"

            results.append(
                {
                    "tool": tool_name,
                    "args": tool_args,
                    "result": str(result),
                }
            )

        return results

    def _append_tool_messages(self, messages: list[dict], tool_calls: list[dict], tool_results: list[dict]):
        """将工具结果追加到消息列表，供下一轮 LLM 观察。"""
        for call, result in zip(tool_calls, tool_results):
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result["result"],
                }
            )

    def _save_tool_results(self, user_id: str, step: int, tool_results: list[dict]):
        """把工具调用历史写入工作记忆，供下一轮规划使用。"""
        if not tool_results:
            return

        current = self.work_memory.get(user_id) or {}
        history = list(current.get("tool_history", []))
        history.append({"step": step, "tool_calls": tool_results})

        current["last_tool_calls"] = tool_results
        current["tool_history"] = history[-10:]
        current["react_step"] = str(step)
        self.work_memory.set(user_id, current, ttl=self.tool_result_ttl)
        logger.debug(f"[WorkMemory] Saved {len(tool_results)} tool result(s) for {user_id} at step {step}")

    def _build_assistant_message(self, msg: dict) -> dict:
        """构建 assistant message，保留 content 与 tool_calls。"""
        assistant_message = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            assistant_message["tool_calls"] = msg["tool_calls"]
        return assistant_message

    def _parse_tool_args(self, raw_args: Any) -> dict:
        """兼容 tools.arguments 为 JSON 字符串或字典。"""
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                logger.warning(f"[AgentCore] Invalid tool arguments JSON: {raw_args}")
        return {}

    def _find_tool(self, name: str):
        for t in self.tools:
            if t.name == name:
                return t
        return None

    def _build_system_prompt(self, relevant_memories: list[str], working_ctx: dict | None) -> str:
        parts = [
            "你是 HangClaw 智能助手，可以使用工具完成用户请求。",
            "请用中文回复。",
            "你必须采用 ReAct 式多步执行：先理解任务并形成简短计划，再按步骤行动，必要时连续多轮调用工具，直到任务真正完成。",
            "当任务需要多步处理时，请先明确接下来要做的步骤；如有必要，可调用 set_context 保存 plan、current_step、result_summary 等状态。",
            "不要只进行一轮工具调用就仓促结束；若问题尚未解决，请基于上一步观察继续调用工具或调整计划。",
            "当已有足够信息时，再给出最终答复；最终答复要简洁总结完成情况与关键结果。",
        ]
        if relevant_memories:
            parts.append("## 相关记忆\n" + "\n".join(f"- {m}" for m in relevant_memories))
        if working_ctx:
            parts.append(f"## 工作上下文\n{working_ctx}")
        return "\n\n".join(parts)
