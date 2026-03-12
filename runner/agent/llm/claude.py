"""
Anthropic Claude LLM Provider
"""

from __future__ import annotations
import os
from typing import Any
import httpx

from utils.logger import logger


class ClaudeProvider:
    def __init__(self, config: dict):
        self.api_key = os.getenv("CLAUDE_API_KEY", "")
        self.base_url = "https://api.anthropic.com/v1"
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.7)

    async def chat(self, messages: list[dict], model: str = "claude-sonnet-4-20250514", tools: list[dict] | None = None, **kwargs) -> dict:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # Claude Messages API 格式：system 单独字段
        system = ""
        api_messages = []
        for m in messages:
            if m["role"] == "system":
                system += m["content"] + "\n"
            else:
                api_messages.append(m)

        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "messages": api_messages,
        }
        if system.strip():
            payload["system"] = system.strip()
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self.base_url}/messages", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # 转换为统一格式
        content = ""
        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]

        return {
            "message": {"role": "assistant", "content": content},
            "usage": data.get("usage"),
        }
