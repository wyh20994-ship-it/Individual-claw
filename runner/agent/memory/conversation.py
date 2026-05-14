from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agent.schemas import ConversationEntry
from utils.logger import logger


class ConversationMemory:
    def __init__(self, config: dict):
        self.max_turns = int(config.get("max_turns", 50))
        self.base_dir = Path(config.get("dir", "./runner/data/memory/conversation"))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _date_key(self, when: datetime | None = None) -> str:
        return (when or datetime.now()).strftime("%Y-%m-%d")

    def _file_path(self, when: datetime | None = None) -> Path:
        return self.base_dir / f"{self._date_key(when)}.jsonl"

    def get_history(self, user_id: str, turns: int | None = None) -> list[dict]:
        entries = self.get_today_entries(user_id)
        limit = (turns or self.max_turns) * 2
        return [{"role": entry.role, "content": entry.content} for entry in entries[-limit:]]

    def get_today_entries(self, user_id: str | None = None) -> list[ConversationEntry]:
        fp = self._file_path()
        if not fp.exists():
            return []

        entries: list[ConversationEntry] = []
        with open(fp, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = ConversationEntry.model_validate(json.loads(line))
                if user_id is None or entry.user_id == user_id:
                    entries.append(entry)
        return entries

    def read_day_text(self, when: datetime | None = None) -> str:
        fp = self._file_path(when)
        if not fp.exists():
            return ""
        return fp.read_text(encoding="utf-8")

    def add_turn(
        self,
        user_id: str,
        role: str,
        content: str,
        channel: str | None = None,
        message_id: str | None = None,
    ):
        entry = ConversationEntry(
            user_id=user_id,
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            channel=channel,
            message_id=message_id,
        )
        fp = self._file_path()
        fp.parent.mkdir(parents=True, exist_ok=True)
        with open(fp, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.model_dump(), ensure_ascii=False) + "\n")

    def clear(self, user_id: str):
        fp = self._file_path()
        if not fp.exists():
            return

        kept: list[str] = []
        with open(fp, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = ConversationEntry.model_validate(json.loads(line))
                if entry.user_id != user_id:
                    kept.append(line)
        fp.write_text("".join(kept), encoding="utf-8")
        logger.info(f"[ConvMemory] Cleared today's history for {user_id}")
