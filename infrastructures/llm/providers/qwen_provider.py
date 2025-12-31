# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Qwen provider adapter.

from __future__ import annotations

from infrastructures.llm.clients.openai_compatible_client import OpenAICompatibleClient
from infrastructures.llm.providers.openai_compatible_provider_base import OpenAICompatibleProviderBase
from infrastructures.vconfig import vconfig


class QwenProvider(OpenAICompatibleProviderBase):
    """Qwen provider.

    In many deployments, Qwen is exposed via an OpenAI-compatible gateway.
    """

    def __init__(self) -> None:
        client = OpenAICompatibleClient(
            base_url=str(vconfig.qwen_base_url),
            api_key=str(vconfig.qwen_api_key),
            timeout_seconds=int(vconfig.qwen_timeout_seconds),
            provider_tag="qwen",
        )
        super().__init__(provider_name="qwen", client=client)
