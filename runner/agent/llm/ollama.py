"""
Ollama Local LLM Provider
"""

from __future__ import annotations
import os
from typing import Any
import httpx

from utils.logger import logger


class OllamaProvider:
    def __init__(self, config: dict):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.default_model = config.get("default_model", "qwen2.5:7b")

    async def chat(self, messages: list[dict], model: str | None = None, tools: list[dict] | None = None, **kwargs) -> dict:
        model = model or self.default_model

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return {
            "message": data.get("message", {}),
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        }
