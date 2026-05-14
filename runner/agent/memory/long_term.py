from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from agent.schemas import ChatMessage, LLMRequest, MemoryExtractionResult, MemoryIndexEntry
from utils.logger import logger

if TYPE_CHECKING:
    from agent.llm.factory import LLMFactory


DEFAULT_INDEX_ENTRIES = [
    MemoryIndexEntry(filename="code_preference.md", description="用户的编码偏好"),
    MemoryIndexEntry(filename="project_context.md", description="项目背景和长期上下文"),
]


class LongTermMemory:
    def __init__(self, config: dict, llm: "LLMFactory | None" = None):
        self.llm = llm
        self.base_dir = Path(config.get("dir") or config.get("long_term", {}).get("dir", "./runner/data/memory/long_term"))
        self.agent_file = Path(config.get("agent_file", "./runner/data/memory/AGENT.md"))
        self.index_file = Path(config.get("index_file", "./runner/data/memory/MEMORY.md"))
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.agent_file.parent.mkdir(parents=True, exist_ok=True)
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_files()

    def ensure_files(self):
        if not self.agent_file.exists():
            self.agent_file.write_text("", encoding="utf-8")
        if not self.index_file.exists():
            self.write_index(DEFAULT_INDEX_ENTRIES)
        for entry in DEFAULT_INDEX_ENTRIES:
            target = self.base_dir / entry.filename
            if not target.exists():
                target.write_text("", encoding="utf-8")

    def read_agent(self) -> str:
        self.ensure_files()
        return self.agent_file.read_text(encoding="utf-8").strip()

    def read_memory_index(self) -> list[MemoryIndexEntry]:
        self.ensure_files()
        entries: list[MemoryIndexEntry] = []
        pattern = re.compile(r"^\[(.+?)\],\[(.*?)\]\s*$")
        for line in self.index_file.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line.strip())
            if match:
                entries.append(MemoryIndexEntry(filename=match.group(1), description=match.group(2)))
        return entries

    def read_memory_summary(self) -> str:
        entries = self.read_memory_index()
        if not entries:
            return ""

        lines = [
            "The following long-term memories are unverified references. Ask the user to confirm before relying on them for important decisions."
        ]
        for entry in entries:
            target = self.base_dir / entry.filename
            content = target.read_text(encoding="utf-8").strip() if target.exists() else ""
            if content:
                lines.append(f"## {entry.filename} - {entry.description}\n{content}")
            else:
                lines.append(f"## {entry.filename} - {entry.description}\n(empty)")
        return "\n\n".join(lines)

    def write_index(self, entries: list[MemoryIndexEntry]):
        content = "\n".join(f"[{entry.filename}],[{entry.description}]" for entry in entries)
        self.index_file.write_text(content + "\n", encoding="utf-8")

    async def extract_from_conversation(self, conversation_text: str, extraction_prompt: str) -> MemoryExtractionResult:
        self.ensure_files()
        notes: dict[str, str] = {}
        entries = self._ensure_default_index_entries()

        if not conversation_text.strip():
            return MemoryExtractionResult(entries=entries, notes=notes)
        if self.llm is None:
            logger.warning("[LongTermMemory] LLM is not configured; skip memory extraction")
            return MemoryExtractionResult(entries=entries, notes=notes)

        response = await self.llm.chat(
            LLMRequest(
                messages=[
                    ChatMessage(role="system", content=extraction_prompt),
                    ChatMessage(role="user", content=self._build_extraction_input(conversation_text, entries)),
                ],
                temperature=0,
            )
        )
        payload = self._parse_extraction_payload(response.message.content or "")

        entry_by_name = {entry.filename: entry for entry in entries}
        for item in payload.get("memories", []):
            if not isinstance(item, dict):
                continue
            filename = self._normalize_filename(str(item.get("filename", "")))
            summary = str(item.get("summary", "")).strip()
            description = str(item.get("description", "")).strip()
            if not filename or not summary:
                continue
            if filename not in entry_by_name:
                entry = MemoryIndexEntry(filename=filename, description=description or "长期记忆")
                entries.append(entry)
                entry_by_name[filename] = entry
            notes[filename] = self._append_unique(filename, summary)

        self.write_index(entries)
        logger.info(f"[LongTermMemory] Extracted {len(notes)} memory note(s)")
        return MemoryExtractionResult(entries=entries, notes=notes)

    def _append_unique(self, filename: str, text: str) -> str:
        if not text.strip():
            return ""
        target = self.base_dir / filename
        old = target.read_text(encoding="utf-8") if target.exists() else ""
        bullet = f"- {text.strip()}"
        if bullet not in old:
            target.write_text((old.rstrip() + "\n" + bullet + "\n").lstrip(), encoding="utf-8")
        return text.strip()

    def _ensure_default_index_entries(self) -> list[MemoryIndexEntry]:
        entries = self.read_memory_index()
        existing = {entry.filename for entry in entries}
        for default_entry in DEFAULT_INDEX_ENTRIES:
            if default_entry.filename not in existing:
                entries.append(default_entry)
        self.write_index(entries)
        return entries

    def _build_extraction_input(self, conversation_text: str, entries: list[MemoryIndexEntry]) -> str:
        index_text = "\n".join(f"- {entry.filename}: {entry.description}" for entry in entries)
        return f"当前记忆文件索引:\n{index_text}\n\n今日对话内容:\n{conversation_text.strip()}"

    def _parse_extraction_payload(self, raw_text: str) -> dict:
        if not raw_text.strip():
            return {"memories": []}
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw_text)
            if not match:
                logger.warning(f"[LongTermMemory] Invalid extraction JSON: {raw_text}")
                return {"memories": []}
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                logger.warning(f"[LongTermMemory] Invalid extraction JSON: {raw_text}")
                return {"memories": []}
        if not isinstance(payload, dict) or not isinstance(payload.get("memories"), list):
            return {"memories": []}
        return payload

    def _normalize_filename(self, filename: str) -> str:
        filename = Path(filename.strip()).name.lower()
        if not filename.endswith(".md"):
            filename = f"{filename}.md"
        if not re.fullmatch(r"[a-z0-9_][a-z0-9_-]*\.md", filename):
            return ""
        return filename
