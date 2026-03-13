import json
import logging
from typing import Optional, Any
from openai import AsyncOpenAI
from litellm import Router
from orion.core.config import settings, SEED_SUPPORTED_PROVIDERS, EMBEDDING_MODEL
from orion.schemas.settings import ProviderConfig
from orion.llm.mock import MockLLM
from orion.llm.config import config_builder
from orion.core.resilience import llm_circuit
from orion.core.metrics import llm_api_errors_total

logger = logging.getLogger(__name__)

class LiteLLMManager:
    """In-process LiteLLM Router wrapper with direct OpenAI SDK fallback for NVIDIA NIM."""

    def __init__(self):
        self._router: Optional[Router] = None
        self._mock = MockLLM()
        self._provider_configs: dict[str, ProviderConfig] = {}
        self._openai_client: Optional[AsyncOpenAI] = None
        # Maps router alias ("planning"/"fast") -> actual model name on NVIDIA NIM
        self._model_map: dict[str, str] = {}

    def configure(self, providers: list[ProviderConfig]) -> None:
        self._provider_configs.clear()
        self._model_map.clear()
        for p in providers:
            if p.enabled:
                self._provider_configs[p.provider] = p

        router_config = config_builder.build(providers)

        if router_config["model_list"]:
            self._router = Router(**router_config)
            logger.info(f"Configured LiteLLM Router with {len(router_config['model_list'])} models")
            # Build model alias map for direct OpenAI SDK calls
            for entry in router_config["model_list"]:
                alias = entry["model_name"]
                raw_model = entry["litellm_params"]["model"]
                # Strip the "openai/" prefix that LiteLLM uses for provider routing
                actual_model = raw_model.split("openai/", 1)[-1] if raw_model.startswith("openai/") else raw_model
                self._model_map[alias] = actual_model
        else:
            self._router = None
            logger.warning("No active LLM providers configured")

        # Build direct OpenAI client for NVIDIA NIM
        for p in providers:
            if p.enabled and p.base_url and "nvidia" in p.base_url:
                self._openai_client = AsyncOpenAI(
                    base_url=p.base_url,
                    api_key=p.api_key,
                )
                logger.info("Configured direct OpenAI client for NVIDIA NIM")
                break

    def is_configured(self) -> bool:
        return self._router is not None

    def _seed_param(self, provider: str, seed: Optional[int]) -> dict:
        if seed is not None and provider in SEED_SUPPORTED_PROVIDERS:
            return {"seed": seed}
        return {}

    def _lazy_init(self) -> None:
        """Auto-build router from environment variables if unconfigured."""
        import sys
        try:
            if not self._router:
                if settings.NVIDIA_API_KEY:
                    self.configure([ProviderConfig(
                        provider="openai",
                        model_planning="openai/nvidia/nemotron-3-super-120b-a12b",
                        model_fast="openai/qwen/qwen2-7b-instruct",
                        api_key=settings.NVIDIA_API_KEY,
                        base_url="https://integrate.api.nvidia.com/v1",
                        planning_extra_body={"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384},
                        enabled=True,
                    )])
                    logger.info("Lazy-initialized LiteLLM for NVIDIA NIM (Nemotron & Qwen)")
                elif settings.OPENROUTER_API_KEY:
                    self.configure([ProviderConfig(
                        provider="openrouter",
                        model_planning="openrouter/anthropic/claude-3.5-sonnet",
                        model_fast="openrouter/openai/gpt-4o-mini",
                        api_key=settings.OPENROUTER_API_KEY,
                        base_url="https://openrouter.ai/api/v1",
                        enabled=True,
                    )])
                    logger.info("Lazy-initialized LiteLLM via OpenRouter")
        except Exception as e:
            import traceback
            sys.stderr.write(f"LAZY_INIT_FAILED: {e}\n{traceback.format_exc()}\n")
            logger.error(f"LAZY_INIT_FAILED: {e}")

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

        self._lazy_init()
        if not self._router:
            raise RuntimeError("LiteLLM router not configured. Cannot generate completion.")

        try:
            # Use direct OpenAI SDK for NVIDIA NIM to bypass LiteLLM's
            # broken streaming parser (content=None on all chunks).
            if self._openai_client and model in self._model_map:
                actual_model = self._model_map[model]
                logger.debug(f"Direct OpenAI call: alias={model} -> model={actual_model}")

                stream = await self._openai_client.chat.completions.create(
                    model=actual_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=True,
                )

                collected = []
                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        collected.append(delta.content)

                result = "".join(collected)
                if not result:
                    raise RuntimeError(f"LLM returned empty response for model={actual_model}")
                return result
            else:
                # Fallback: use LiteLLM router for non-NVIDIA providers
                params = self._seed_param("generic", seed)
                params.update({
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                })
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

        self._lazy_init()
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
