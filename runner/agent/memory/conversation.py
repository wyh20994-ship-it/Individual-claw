"""
对话记忆 — 基于 JSONL 的持久化对话历史
每个 user_id 对应一个 .jsonl 文件
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

from utils.logger import logger


class ConversationMemory:
    def __init__(self, config: dict):
        self.max_turns = config.get("max_turns", 50)
        base = os.getenv("MEMORY_CONVERSATIONS_DIR", "./data/memory/conversations")
        self.base_dir = Path(base)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # 内存缓存：{ user_id: [messages] }
        self._cache: dict[str, list[dict]] = {}

    def _file_path(self, user_id: str) -> Path:
        # 使用安全的文件名
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
        return self.base_dir / f"{safe_id}.jsonl"

    def get_history(self, user_id: str) -> list[dict]:
        if user_id in self._cache:
            return self._cache[user_id][-self.max_turns * 2 :]

        # 从文件加载
        fp = self._file_path(user_id)
        messages: list[dict] = []
        if fp.exists():
            with open(fp, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        messages.append(json.loads(line))

        # 只保留最近 N 轮
        messages = messages[-self.max_turns * 2 :]
        self._cache[user_id] = messages
        return messages

    def add_turn(self, user_id: str, role: str, content: str):
        entry = {"role": role, "content": content}
        if user_id not in self._cache:
            self._cache[user_id] = []
        self._cache[user_id].append(entry)

        # 追加写入文件
        fp = self._file_path(user_id)
        with open(fp, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # 截断内存缓存
        if len(self._cache[user_id]) > self.max_turns * 2:
            self._cache[user_id] = self._cache[user_id][-self.max_turns * 2 :]

    def clear(self, user_id: str):
        self._cache.pop(user_id, None)
        fp = self._file_path(user_id)
        if fp.exists():
            fp.unlink()
        logger.info(f"[ConvMemory] Cleared history for {user_id}")
