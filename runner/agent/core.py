from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from agent.llm.factory import LLMFactory
from agent.memory.conversation import ConversationMemory
from agent.memory.long_term import LongTermMemory
from agent.memory.semantic import SemanticMemory
from agent.memory.working import WorkingMemory
from agent.sandbox import SandboxClient
from agent.schemas import ChatMessage, LLMRequest, PlanResult, ToolResult
from agent.services.scheduler_store import ScheduledTask, SchedulerStore
from agent.skills.loader import Skill, SkillLoader
from agent.tools import get_all_tools
from agent.tools.context_tool import SetContextTool
from utils.logger import logger


SYSTEM_PROMPT = """You are Individual-Claw, a practical personal AI agent.
Follow user-written AGENT.md instructions first. Treat extracted MEMORY.md content as unverified reference only.
If a memory would materially affect a decision, ask the user to confirm that it is still correct before relying on it.
Use tools only through the structured tool-calling interface."""

MEMORY_EXTRACT_TASK_NAME = "memory.extract_daily"
SCHEDULE_SYNC_JOB_ID = "scheduler.sync_database"
SCHEDULE_SYNC_SECONDS = 30
DEFAULT_MEMORY_EXTRACT_PROMPT = """请分析今天的对话内容，提取值得长期保存的信息。

要求：
1. 不要按关键词提取，要根据对话内容判断。
2. 只保存长期稳定、未来会影响协作的信息。
3. 用简洁总结写入合适的长期记忆文件。
"""


DEFAULT_SCHEDULED_TASKS = [
    {
        "name": MEMORY_EXTRACT_TASK_NAME,
        "cron_config_path": ("runner", "memory", "extract_cron"),
        "default_cron": "0 0 * * *",
        "description": "每天从对话中提取长期记忆",
        "prompt": DEFAULT_MEMORY_EXTRACT_PROMPT,
        "payload": {"type": "memory_extract"},
        "enabled": True,
    }
]


class AgentCore:
    def __init__(self, config: dict):
        self.config = config
        runner_cfg = config.get("runner", {})
        memory_cfg = runner_cfg.get("memory", {})

        self.llm = LLMFactory(runner_cfg.get("llm", {}))
        self.conv_memory = ConversationMemory(memory_cfg.get("conversation", {}))
        self.long_memory = LongTermMemory(memory_cfg, llm=self.llm)
        self.sem_memory = SemanticMemory(memory_cfg.get("semantic", {}))
        self.work_memory = WorkingMemory(memory_cfg.get("working", {}))

        self.sandbox = SandboxClient(runner_cfg.get("sandbox", {}))
        self.tools = get_all_tools(runner_cfg.get("tools", {}), sandbox_client=self.sandbox)
        self.tools.append(SetContextTool(self.work_memory))
        self.skill_loader = SkillLoader(config)

        agent_cfg = runner_cfg.get("agent", {})
        self.max_reasoning_steps = int(agent_cfg.get("max_reasoning_steps", 6))
        self.tool_result_ttl = int(agent_cfg.get("tool_result_ttl", 300))

        self.planner_cfg = runner_cfg.get("planner", {})
        self.planner_enabled = bool(self.planner_cfg.get("enabled", False))
        self.planner_triggers = list(
            self.planner_cfg.get("trigger_keywords", ["/规划", "/plan", "制定计划", "分解任务"])
        )
        scheduler_cfg = runner_cfg.get("scheduler", {})
        self.scheduler_store = SchedulerStore(scheduler_cfg.get("db_url", "sqlite:///./data/scheduler/tasks.db"))
        self.scheduler: AsyncIOScheduler | None = None

    async def initialize(self):
        await self.sem_memory.initialize()
        self.long_memory.ensure_files()
        await self.sandbox.sync_skills(self.skill_loader.directory)
        self._start_memory_scheduler()
        logger.info("[AgentCore] Initialized")

    async def chat(self, user_id: str, content: str, **kwargs: Any) -> str:
        channel = kwargs.get("channel")
        message_id = kwargs.get("messageId")
        matched_skill = self.skill_loader.match_skill(content)

        self.conv_memory.add_turn(user_id, "user", content, channel=channel, message_id=message_id)
        messages = self._build_messages(user_id, matched_skill)

        plan_payload: PlanResult | None = None
        if self._should_run_planner(content):
            plan_payload = await self._create_structured_plan(messages, user_id, matched_skill)
            self._save_plan(user_id, plan_payload, matched_skill)
            messages.append(ChatMessage(role="assistant", content=self._format_plan_message(plan_payload)))

        assistant_content = await self._run_react_loop(messages, user_id, plan_payload)
        self.conv_memory.add_turn(user_id, "assistant", assistant_content, channel=channel, message_id=message_id)
        await self.sem_memory.add(content, metadata={"user_id": user_id, "role": "user"})
        return assistant_content

    def _build_messages(self, user_id: str, matched_skill: Skill | None) -> list[ChatMessage]:
        parts = [SYSTEM_PROMPT]

        agent_text = self.long_memory.read_agent()
        if agent_text:
            parts.append(f"## AGENT.md\n{agent_text}")

        if matched_skill:
            parts.append(f"## Skill Description\n{matched_skill.prompt_description()}")

        memory_summary = self.long_memory.read_memory_summary()
        if memory_summary:
            parts.append(f"## MEMORY.md\n{memory_summary}")

        history = self.conv_memory.get_history(user_id)
        messages = [ChatMessage(role="system", content="\n\n".join(parts))]
        messages.extend(ChatMessage.model_validate(item) for item in history)
        return messages

    def _should_run_planner(self, content: str) -> bool:
        if not self.planner_enabled:
            return False
        return any(keyword in content for keyword in self.planner_triggers)

    async def _create_structured_plan(
        self, messages: list[ChatMessage], user_id: str, matched_skill: Skill | None
    ) -> PlanResult:
        provider, model = self.llm.planner_config(self.planner_cfg)
        planning_messages = [
            ChatMessage(
                role="system",
                content=(
                    "Return only JSON matching this schema: "
                    '{"goal":"string","plan":["step"],"need_tools":true,"thought":"string"}'
                ),
            ),
            ChatMessage(
                role="user",
                content=json.dumps(
                    {
                        "user_id": user_id,
                        "skill": matched_skill.name if matched_skill else None,
                        "messages": [m.model_dump(exclude_none=True) for m in messages],
                    },
                    ensure_ascii=False,
                ),
            ),
        ]
        response = await self.llm.chat(LLMRequest(messages=planning_messages, provider=provider, model=model))
        return self._parse_plan_payload(response.message.content)

    async def _run_react_loop(
        self, messages: list[ChatMessage], user_id: str, plan_payload: PlanResult | None
    ) -> str:
        tool_schemas = [t.schema() for t in self.tools]
        final_content = ""

        for step in range(1, self.max_reasoning_steps + 1):
            response = await self.llm.chat(LLMRequest(messages=messages, tools=tool_schemas))
            msg = response.message
            tool_calls = msg.tool_calls or []
            content = msg.content or ""
            final_content = content or final_content

            messages.append(ChatMessage(role="assistant", content=content, tool_calls=tool_calls or None))
            if not tool_calls:
                return self._finalize_answer(content, plan_payload)

            tool_results = await self._execute_tool_calls(tool_calls, user_id)
            self._append_tool_messages(messages, tool_calls, tool_results)
            self._save_tool_results(user_id, step, tool_results)

        logger.warning(f"[AgentCore] ReAct loop reached max steps for {user_id}")
        return self._finalize_answer(final_content or "Reached max reasoning steps without a final answer.", plan_payload)

    async def _execute_tool_calls(self, tool_calls: list[dict], user_id: str) -> list[ToolResult]:
        results: list[ToolResult] = []
        for call in tool_calls:
            function = call.get("function", {})
            tool_name = function.get("name", "")
            tool_args = self._parse_tool_args(function.get("arguments"))
            tool = self._find_tool(tool_name)
            if not tool:
                results.append(ToolResult(tool=tool_name, args=tool_args, result=f"Tool '{tool_name}' not found"))
                continue
            try:
                result = await tool.execute(**tool_args, user_id=user_id)
            except Exception as e:
                logger.exception(f"[AgentCore] Tool execution failed: {tool_name}")
                result = f"Tool execution failed: {e}"
            results.append(ToolResult(tool=tool_name, args=tool_args, result=str(result)))
        return results

    def _append_tool_messages(self, messages: list[ChatMessage], tool_calls: list[dict], tool_results: list[ToolResult]):
        for call, result in zip(tool_calls, tool_results):
            messages.append(
                ChatMessage(role="tool", tool_call_id=call.get("id", ""), content=result.result)
            )

    def _parse_tool_args(self, raw_args: Any) -> dict:
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                logger.warning(f"[AgentCore] Invalid tool arguments JSON: {raw_args}")
        return {}

    def _parse_plan_payload(self, raw_text: str) -> PlanResult:
        if not raw_text.strip():
            return PlanResult()
        try:
            return PlanResult.model_validate_json(raw_text)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", raw_text)
            if match:
                try:
                    return PlanResult.model_validate_json(match.group(0))
                except Exception:
                    logger.warning(f"[AgentCore] Invalid planning JSON: {raw_text}")
        return PlanResult()

    def _format_plan_message(self, plan_payload: PlanResult) -> str:
        return "plan: " + json.dumps(plan_payload.plan, ensure_ascii=False)

    def _finalize_answer(self, content: str, plan_payload: PlanResult | None) -> str:
        if not plan_payload or not plan_payload.plan:
            return content
        return f"plan: {json.dumps(plan_payload.plan, ensure_ascii=False)}\n\n{content}"

    def _save_plan(self, user_id: str, plan_payload: PlanResult, matched_skill: Skill | None):
        current = self.work_memory.get(user_id) or {}
        current["goal"] = plan_payload.goal
        current["plan"] = plan_payload.plan
        current["need_tools"] = str(plan_payload.need_tools).lower()
        current["plan_thought"] = plan_payload.thought
        if matched_skill:
            current["matched_skill"] = matched_skill.name
        self.work_memory.set(user_id, current, ttl=self.tool_result_ttl)

    def _save_tool_results(self, user_id: str, step: int, tool_results: list[ToolResult]):
        current = self.work_memory.get(user_id) or {}
        history = list(current.get("tool_history", []))
        history.append({"step": step, "tool_calls": [r.model_dump() for r in tool_results]})
        current["last_tool_calls"] = [r.model_dump() for r in tool_results]
        current["tool_history"] = history[-10:]
        current["react_step"] = str(step)
        self.work_memory.set(user_id, current, ttl=self.tool_result_ttl)

    def _find_tool(self, name: str):
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def _start_memory_scheduler(self):
        self._ensure_default_scheduled_tasks_from_database_defaults()
        self.scheduler = AsyncIOScheduler()
        self._sync_scheduled_tasks()
        self.scheduler.add_job(
            self._sync_scheduled_tasks,
            "interval",
            seconds=SCHEDULE_SYNC_SECONDS,
            id=SCHEDULE_SYNC_JOB_ID,
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("[Scheduler] Database-backed scheduler started")

    def _ensure_default_scheduled_tasks_from_database_defaults(self):
        for default_task in DEFAULT_SCHEDULED_TASKS:
            cron = self._get_config_value(
                default_task["cron_config_path"],
                default_task["default_cron"],
            )
            task = self.scheduler_store.ensure_task(
                name=default_task["name"],
                cron=cron,
                description=default_task["description"],
                prompt=default_task["prompt"],
                payload=default_task["payload"],
                enabled=default_task["enabled"],
            )
            if not (task.prompt or "").strip():
                self.scheduler_store.upsert_task(
                    name=task.name,
                    cron=task.cron,
                    description=task.description,
                    prompt=default_task["prompt"],
                    payload=task.payload,
                    enabled=task.enabled,
                    next_run=task.next_run,
                )

    def _get_config_value(self, path: tuple[str, ...], default: Any) -> Any:
        value: Any = self.config
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    def _ensure_default_scheduled_tasks(self):
        memory_cfg = self.config.get("runner", {}).get("memory", {})
        cron = memory_cfg.get("extract_cron", "0 0 * * *")
        task = self.scheduler_store.ensure_task(
            name=MEMORY_EXTRACT_TASK_NAME,
            cron=cron,
            description="每天从对话中提取长期记忆",
            prompt=DEFAULT_MEMORY_EXTRACT_PROMPT,
            payload={"type": "memory_extract"},
            enabled=True,
        )
        if not (task.prompt or "").strip():
            self.scheduler_store.upsert_task(
                name=task.name,
                cron=task.cron,
                description=task.description,
                prompt=DEFAULT_MEMORY_EXTRACT_PROMPT,
                payload=task.payload,
                enabled=task.enabled,
                next_run=task.next_run,
            )

    def _sync_scheduled_tasks(self):
        if self.scheduler is None:
            return

        enabled_tasks = self.scheduler_store.list_enabled()
        enabled_job_ids = {self._task_job_id(task.name) for task in enabled_tasks}
        for job in self.scheduler.get_jobs():
            if job.id == SCHEDULE_SYNC_JOB_ID:
                continue
            if job.id not in enabled_job_ids:
                self.scheduler.remove_job(job.id)

        for task in enabled_tasks:
            self._schedule_database_task(task)

    def _schedule_database_task(self, task: ScheduledTask):
        if self.scheduler is None:
            return
        parts = task.cron.split()
        if len(parts) != 5:
            logger.warning(f"[Scheduler] Invalid cron for {task.name}: {task.cron}")
            return
        self.scheduler.add_job(
            self._run_scheduled_task,
            "cron",
            args=[task.name],
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            id=self._task_job_id(task.name),
            replace_existing=True,
        )
        job = self.scheduler.get_job(self._task_job_id(task.name))
        self.scheduler_store.update_next_run(task.name, getattr(job, "next_run_time", None) if job else None)

    def _task_job_id(self, task_name: str) -> str:
        return f"db_task:{task_name}"

    async def _run_scheduled_task(self, task_name: str):
        task = self.scheduler_store.get_task(task_name)
        if task is None or not task.enabled:
            return
        payload = task.payload or {}
        if payload.get("type") == "memory_extract":
            await self.extract_memory(task.prompt)
        else:
            await self._run_llm_scheduled_task(task)
        job = self.scheduler.get_job(self._task_job_id(task.name)) if self.scheduler else None
        self.scheduler_store.mark_run(task.name, datetime.now(), getattr(job, "next_run_time", None) if job else None)

    async def _run_llm_scheduled_task(self, task: ScheduledTask):
        prompt = task.prompt.strip()
        if not prompt:
            logger.warning(f"[Scheduler] Task has no prompt: {task.name}")
            return
        messages = self._build_messages(user_id=f"scheduled:{task.name}", matched_skill=None)
        messages.append(ChatMessage(role="user", content=prompt))
        await self._run_react_loop(messages, user_id=f"scheduled:{task.name}", plan_payload=None)

    async def extract_memory(self, prompt: str):
        text = self.conv_memory.read_day_text()
        if not text.strip():
            logger.info("[Memory] No conversation text to extract")
            return
        prompt = prompt.strip()
        if not prompt:
            logger.warning("[Memory] Memory extraction prompt is empty")
            return
        await self.long_memory.extract_from_conversation(text, prompt)
