"""
LLM Router — 统一入口，根据配置路由到不同的 LLM Provider
"""

from __future__ import annotations
import os
from typing import Any

from agent.llm.deepseek import DeepSeekProvider
from agent.llm.openai_llm import OpenAIProvider
from agent.llm.claude import ClaudeProvider
from agent.llm.ollama import OllamaProvider
from utils.logger import logger

PROVIDERS = {
    "deepseek": DeepSeekProvider,
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
    "ollama": OllamaProvider,
}


class LLMRouter:
    def __init__(self, config: dict):
        self.config = config
        self.default_provider = config.get("default_provider", "deepseek")
        self.default_model = config.get("default_model", "deepseek-chat")
        self._instances: dict[str, Any] = {}

        # 预初始化已启用的 provider
        for name, cfg in config.get("providers", {}).items():
            if cfg.get("enabled"):
                cls = PROVIDERS.get(name)
                if cls:
                    self._instances[name] = cls(cfg)
                    logger.info(f"[LLMRouter] Provider '{name}' loaded")

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        provider: str | None = None,
        model: str | None = None,
        **kwargs,
    ) -> dict:
        provider = provider or self.default_provider
        model = model or self.default_model
        instance = self._instances.get(provider)
        if not instance:
            raise ValueError(f"LLM provider '{provider}' is not enabled or unknown")
        return await instance.chat(messages, model=model, tools=tools, **kwargs)
