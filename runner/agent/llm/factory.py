from __future__ import annotations

from typing import Any

from agent.llm.claude import ClaudeProvider
from agent.llm.deepseek import DeepSeekProvider
from agent.llm.ollama import OllamaProvider
from agent.llm.openai_llm import OpenAIProvider
from agent.schemas import LLMRequest, LLMResponse
from utils.logger import logger


PROVIDERS = {
    "deepseek": DeepSeekProvider,
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
    "ollama": OllamaProvider,
}


class LLMFactory:
    def __init__(self, config: dict):
        self.config = config
        self.default_provider = config.get("default_provider", "deepseek")
        self.default_model = config.get("default_model", "deepseek-chat")
        self._instances: dict[str, Any] = {}

        for name, provider_cfg in config.get("providers", {}).items():
            if not provider_cfg.get("enabled"):
                continue
            provider_cls = PROVIDERS.get(name)
            if not provider_cls:
                logger.warning(f"[LLMFactory] Unknown provider skipped: {name}")
                continue
            self._instances[name] = provider_cls(provider_cfg)
            logger.info(f"[LLMFactory] Provider loaded: {name}")

    def get(self, provider: str | None = None):
        provider_name = provider or self.default_provider
        instance = self._instances.get(provider_name)
        if not instance:
            raise ValueError(f"LLM provider '{provider_name}' is not enabled or unknown")
        return instance

    async def chat(self, request: LLMRequest | dict) -> LLMResponse:
        if isinstance(request, dict):
            request = LLMRequest.model_validate(request)

        provider_name = request.provider or self.default_provider
        model = request.model or self.default_model
        provider = self.get(provider_name)
        kwargs: dict[str, Any] = {}
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        raw = await provider.chat(
            messages=[m.model_dump(exclude_none=True) for m in request.messages],
            model=model,
            tools=request.tools,
            **kwargs,
        )
        return LLMResponse.model_validate(raw)

    def planner_config(self, planner_cfg: dict) -> tuple[str, str]:
        provider = planner_cfg.get("provider") or self.default_provider
        model = planner_cfg.get("model") or self.default_model
        return provider, model
