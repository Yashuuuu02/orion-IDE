import json
import logging
from typing import Optional, Any
from litellm import Router
from orion.core.config import settings, SEED_SUPPORTED_PROVIDERS, EMBEDDING_MODEL
from orion.schemas.settings import ProviderConfig
from orion.llm.mock import MockLLM
from orion.llm.config import config_builder
from orion.core.resilience import llm_circuit
from orion.core.metrics import llm_api_errors_total

logger = logging.getLogger(__name__)

class LiteLLMManager:
    """In-process LiteLLM Router wrapper"""

    def __init__(self):
        self._router: Optional[Router] = None
        self._mock = MockLLM()
        self._provider_configs: dict[str, ProviderConfig] = {}

    def configure(self, providers: list[ProviderConfig]) -> None:
        self._provider_configs.clear()
        for p in providers:
            if p.enabled:
                self._provider_configs[p.provider] = p

        router_config = config_builder.build(providers)

        if router_config["model_list"]:
            # Replaces self._router in-place for hot reload
            self._router = Router(**router_config)
            logger.info(f"Configured LiteLLM Router with {len(router_config['model_list'])} models")
        else:
            self._router = None
            logger.warning("No active LLM providers configured")

    def is_configured(self) -> bool:
        return self._router is not None

    def _seed_param(self, provider: str, seed: Optional[int]) -> dict:
        if seed is not None and provider in SEED_SUPPORTED_PROVIDERS:
            return {"seed": seed}
        return {}

    async def get_completion(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float = 0.0,
        seed: Optional[int] = None,
        component_name: Optional[str] = None
    ) -> str:

        if settings.MOCK_LLM:
            if not component_name:
                raise ValueError("component_name required for mock LLM completion")
            return self._mock.get_completion(component_name, messages)

        if not self._router:
            raise RuntimeError("LiteLLM router not configured. Cannot generate completion.")

        # Determine the provider from the active config (assuming passing provider str in some wrapper, defaults to generic)
        # Assuming `model` acts as the routing identifier

        provider = "generic" # Default if not matched
        # Simple extraction for seeding - we check if model name implies provider
        if "openai" in model or "gpt" in model:
            provider = "openai"
        elif "groq" in model:
            provider = "groq"
        elif "nvidia" in model:
            provider = "nvidia_nim"
        elif "anthropic" in model or "claude" in model:
            provider = "anthropic"

        params = self._seed_param(provider, seed)
        params.update({
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        })

        try:
            response = await llm_circuit.call(self._router.acompletion(**params))
            return response.choices[0].message.content
        except Exception as e:
            err_provider = model.split("/")[0] if "/" in model else "unknown"
            llm_api_errors_total.labels(
                provider=err_provider,
                error_type=type(e).__name__
            ).inc()
            raise

    async def get_embedding(self, text: str) -> list[float]:
        if settings.MOCK_LLM:
            return self._mock.get_embedding(text)

        if not self._router:
            raise RuntimeError("LiteLLM router not configured. Cannot generate embedding.")

        # Assuming OpenAI style generic embedding mapping if user passes api_key via router
        response = await self._router.aembedding(
            model=EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding

# Singleton instance
llm_manager = LiteLLMManager()
