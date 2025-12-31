# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Provider registry (singleton instances). Infrastructure-only.

from __future__ import annotations

from functools import lru_cache
from typing import Dict

from domains.llm_model_domain import LlmProvider
from infrastructures.llm.providers import (
    DeepSeekProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAIProvider,
    QwenProvider,
)


@lru_cache(maxsize=1)
def get_provider_registry() -> Dict[str, object]:
    """Create provider singletons.

    The registry is intentionally process-local.
    """

    return {
        LlmProvider.openai.value: OpenAIProvider(),
        LlmProvider.gemini.value: GeminiProvider(),
        LlmProvider.deepseek.value: DeepSeekProvider(),
        LlmProvider.qwen.value: QwenProvider(),
        LlmProvider.ollama.value: OllamaProvider(),
    }


def get_provider(provider: str):
    reg = get_provider_registry()
    return reg.get(str(provider))


async def close_provider_registry() -> None:
    """Best-effort shutdown hook to close provider resources.

    This keeps existing behavior intact (providers are still lazily created
    via get_provider_registry()), while allowing network clients to close
    their connection pools on application shutdown.
    """

    try:
        # If registry hasn't been created yet, do nothing.
        if get_provider_registry.cache_info().currsize <= 0:
            return

        reg = get_provider_registry()
        for p in reg.values():
            aclose = getattr(p, "aclose", None)
            if callable(aclose):
                try:
                    await aclose()
                except Exception:
                    continue
    except Exception:
        # Best-effort: shutdown should not crash.
        return
