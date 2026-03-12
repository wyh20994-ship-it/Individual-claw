"""
工作记忆 — 基于 TTL Cache 的短期上下文缓存
存放当前会话的临时状态（如多轮工具调用中间结果）
"""

from __future__ import annotations
import time
from typing import Any

from utils.logger import logger


class WorkingMemory:
    def __init__(self, config: dict):
        self.default_ttl = config.get("default_ttl", 3600)
        # { key: (value, expire_at) }
        self._store: dict[str, tuple[Any, float]] = {}

    def set(self, key: str, value: Any, ttl: int | None = None):
        expire_at = time.time() + (ttl or self.default_ttl)
        self._store[key] = (value, expire_at)

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expire_at = entry
        if time.time() > expire_at:
            del self._store[key]
            return None
        return value

    def delete(self, key: str):
        self._store.pop(key, None)

    def cleanup(self):
        """清理所有已过期条目"""
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]
        if expired:
            logger.debug(f"[WorkingMemory] Cleaned {len(expired)} expired entries")
