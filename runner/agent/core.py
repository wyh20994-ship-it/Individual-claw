"""
AgentCore — HangClaw 的 Agent 核心执行引擎
负责编排 LLM、Memory、Tools、Skills 完成对话
"""

from __future__ import annotations
import json
import re
from typing import Any

from agent.llm.router import LLMRouter
from agent.memory.conversation import ConversationMemory
from agent.memory.semantic import SemanticMemory
from agent.memory.working import WorkingMemory
from agent.tools import get_all_tools
from agent.tools.context_tool import SetContextTool
from agent.skills.loader import Skill, SkillLoader
from utils.logger import logger


class AgentCore:
    """接收用户消息 → 组装 Prompt → 调用 LLM → 解析工具调用 → 返回回复"""

    def __init__(self, config: dict):
        self.config = config
        runner_cfg = config.get("runner", {})

        self.llm = LLMRouter(runner_cfg.get("llm", {}))
        self.conv_memory = ConversationMemory(runner_cfg.get("memory", {}).get("conversation", {}))
        self.sem_memory = SemanticMemory(runner_cfg.get("memory", {}).get("semantic", {}))
        self.work_memory = WorkingMemory(runner_cfg.get("memory", {}).get("working", {}))

        self.tools = get_all_tools(runner_cfg.get("tools", {}))
        self.tools.append(SetContextTool(self.work_memory))
        self.skill_loader = SkillLoader(config)

        agent_cfg = runner_cfg.get("agent", {})
        self.max_reasoning_steps = agent_cfg.get("max_reasoning_steps", 6)
        self.tool_result_ttl = agent_cfg.get("tool_result_ttl", 300)

    async def initialize(self):
        await self.sem_memory.initialize()
        logger.info("[AgentCore] Semantic memory initialized")
        self.skill_loader.start_watching()
        logger.info("[AgentCore] Skill hot-reload watcher started")

    async def chat(self, user_id: str, content: str, **kwargs: Any) -> str:
        history = self.conv_memory.get_history(user_id)
        relevant = await self.sem_memory.query(content, top_k=3)
        context = self.work_memory.get(user_id)
        matched_skill = self.skill_loader.match_skill(content)

        if matched_skill:
            logger.info(f"[AgentCore] Matched skill '{matched_skill.name}' for user {user_id}")

        system_prompt = self._build_system_prompt(relevant, context, matched_skill)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": content})

        plan_payload = await self._create_structured_plan(messages, user_id, matched_skill)
        self._save_plan(user_id, plan_payload, matched_skill)
        messages.append({"role": "assistant", "content": self._format_plan_message(plan_payload)})

        assistant_content = await self._run_react_loop(messages, user_id, plan_payload)

        self.conv_memory.add_turn(user_id, "user", content)
        self.conv_memory.add_turn(user_id, "assistant", assistant_content)
        await self.sem_memory.add(content, metadata={"user_id": user_id, "role": "user"})
        return assistant_content

    async def _create_structured_plan(self, messages: list[dict], user_id: str, matched_skill: Skill | None) -> dict[str, Any]:
        skill_hint = matched_skill.name if matched_skill else "none"
        planning_messages = [
            {
                "role": "system",
                "content": (
                    "你是 Individual-Claw 的任务规划器。请生成简洁、可执行的结构化计划。"
                    "必须输出 JSON，格式严格为："
                    '{"goal":"...","plan":["步骤1","步骤2"],"need_tools":true,"thought":"一句简短说明"}'
                    "不要输出 JSON 以外的任何内容。"
                ),
            },
            {
                "role": "user",
                "content": f"skill={skill_hint}\nuser_id={user_id}\nmessages={json.dumps(messages, ensure_ascii=False)}",
            },
        ]
        response = await self.llm.chat(planning_messages)
        payload = self._parse_plan_payload(response.get("message", {}).get("content") or "")
        if not payload["plan"]:
            payload["plan"] = ["理解用户目标", "根据需要调用工具", "整理结果并回复用户"]
        if not payload["goal"]:
            payload["goal"] = "完成用户请求"
        return payload

    async def _run_react_loop(self, messages: list[dict], user_id: str, plan_payload: dict[str, Any]) -> str:
        tool_schemas = [t.schema() for t in self.tools]
        final_content = ""

        for step in range(1, self.max_reasoning_steps + 1):
            response = await self.llm.chat(messages, tools=tool_schemas)
            msg = response.get("message", {})
            tool_calls = msg.get("tool_calls") or []
            content = msg.get("content") or ""
            final_content = content or final_content

            messages.append(self._build_assistant_message(msg))
            if not tool_calls:
                return self._finalize_answer(content, plan_payload)

            tool_results = await self._execute_tool_calls(tool_calls, user_id)
            self._append_tool_messages(messages, tool_calls, tool_results)
            self._save_tool_results(user_id, step, tool_results)

        logger.warning(f"[AgentCore] ReAct loop reached max steps for {user_id}")
        if final_content:
            return self._finalize_answer(final_content, plan_payload)
        return self._finalize_answer(f"已达到最大执行步数（{self.max_reasoning_steps}），请将任务拆小后再试。", plan_payload)

    async def _execute_tool_calls(self, tool_calls: list[dict], user_id: str) -> list[dict]:
        results: list[dict] = []
        for call in tool_calls:
            tool_name = call["function"]["name"]
            tool_args = self._parse_tool_args(call["function"].get("arguments"))
            tool = self._find_tool(tool_name)
            if not tool:
                results.append({"tool": tool_name, "args": tool_args, "result": f"Tool '{tool_name}' not found"})
                continue
            try:
                result = await tool.execute(**tool_args, user_id=user_id)
            except Exception as e:
                logger.exception(f"[AgentCore] Tool execution failed: {tool_name}")
                result = f"工具执行失败: {e}"
            results.append({"tool": tool_name, "args": tool_args, "result": str(result)})
        return results

    def _append_tool_messages(self, messages: list[dict], tool_calls: list[dict], tool_results: list[dict]):
        for call, result in zip(tool_calls, tool_results):
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result["result"]})

    def _save_plan(self, user_id: str, plan_payload: dict[str, Any], matched_skill: Skill | None):
        current = self.work_memory.get(user_id) or {}
        current["goal"] = plan_payload.get("goal", "")
        current["plan"] = plan_payload.get("plan", [])
        current["need_tools"] = str(plan_payload.get("need_tools", True)).lower()
        current["plan_thought"] = plan_payload.get("thought", "")
        if matched_skill:
            current["matched_skill"] = matched_skill.name
        self.work_memory.set(user_id, current, ttl=self.tool_result_ttl)

    def _save_tool_results(self, user_id: str, step: int, tool_results: list[dict]):
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
        assistant_message = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            assistant_message["tool_calls"] = msg["tool_calls"]
        return assistant_message

    def _parse_tool_args(self, raw_args: Any) -> dict:
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

    def _parse_plan_payload(self, raw_text: str) -> dict[str, Any]:
        payload = {"goal": "", "plan": [], "need_tools": True, "thought": ""}
        if not raw_text.strip():
            return payload
        parsed: dict[str, Any] | None = None
        try:
            maybe = json.loads(raw_text)
            if isinstance(maybe, dict):
                parsed = maybe
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw_text)
            if match:
                try:
                    maybe = json.loads(match.group(0))
                    if isinstance(maybe, dict):
                        parsed = maybe
                except json.JSONDecodeError:
                    logger.warning(f"[AgentCore] Invalid planning JSON: {raw_text}")
        if not parsed:
            return payload
        plan = parsed.get("plan")
        payload["goal"] = str(parsed.get("goal", "") or "")
        payload["plan"] = [str(item) for item in plan] if isinstance(plan, list) else []
        payload["need_tools"] = bool(parsed.get("need_tools", True))
        payload["thought"] = str(parsed.get("thought", "") or "")
        return payload

    def _format_plan_message(self, plan_payload: dict[str, Any]) -> str:
        lines = [
            f"goal: {plan_payload.get('goal', '完成用户请求')}",
            f"plan: {json.dumps(plan_payload.get('plan', []), ensure_ascii=False)}",
        ]
        if plan_payload.get("thought"):
            lines.append(f"thought: {plan_payload['thought']}")
        return "\n".join(lines)

    def _finalize_answer(self, content: str, plan_payload: dict[str, Any]) -> str:
        if not content:
            content = "任务已处理完成。"
        plan_json = json.dumps(plan_payload.get("plan", []), ensure_ascii=False)
        return f"plan: {plan_json}\n\n{content}"

    def _find_tool(self, name: str):
        for t in self.tools:
            if t.name == name:
                return t
        return None

    def _build_skill_section(self, matched_skill: Skill | None) -> str | None:
        if not matched_skill:
            return None
        return (
            f"## 命中技能\n名称: {matched_skill.name}\n描述: {matched_skill.description}\n"
            f"触发词: {', '.join(matched_skill.triggers)}\n\n以下是技能说明，请优先遵循其执行逻辑：\n{matched_skill.content}"
        )

    def _build_system_prompt(self, relevant_memories: list[str], working_ctx: dict | None, matched_skill: Skill | None) -> str:
        parts = [
            "你是 HangClaw 智能助手，可以使用工具完成用户请求。",
            "请用中文回复。",
            "你必须采用 ReAct 式多步执行：先理解任务并形成显式结构化计划，再按步骤行动，必要时连续多轮调用工具，直到任务真正完成。",
            "你在正式执行前必须先得到一个明确计划，格式类似 plan: [步骤1, 步骤2, ...]。执行过程中必须参考当前 plan。",
            "当任务需要多步处理时，请先明确接下来要做的步骤；如有必要，可调用 set_context 保存 plan、current_step、result_summary 等状态。",
            "不要只进行一轮工具调用就仓促结束；若问题尚未解决，请基于上一步观察继续调用工具或调整计划。",
            "如果命中了技能，优先遵循技能说明来规划和执行。",
            "当已有足够信息时，再给出最终答复；最终答复要简洁总结完成情况与关键结果。",
        ]
        if relevant_memories:
            parts.append("## 相关记忆\n" + "\n".join(f"- {m}" for m in relevant_memories))
        if working_ctx:
            parts.append(f"## 工作上下文\n{working_ctx}")
        skill_section = self._build_skill_section(matched_skill)
        if skill_section:
            parts.append(skill_section)
        return "\n\n".join(parts)
