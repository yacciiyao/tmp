# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: DeepSeek provider adapter.

from __future__ import annotations

from infrastructures.llm.clients.openai_compatible_client import OpenAICompatibleClient
from infrastructures.llm.providers.openai_compatible_provider_base import OpenAICompatibleProviderBase
from infrastructures.vconfig import vconfig


class DeepSeekProvider(OpenAICompatibleProviderBase):
    """DeepSeek provider.

    We assume an OpenAI-compatible gateway is used (common in production).
    """

    def __init__(self) -> None:
        client = OpenAICompatibleClient(
            base_url=str(vconfig.deepseek_base_url),
            api_key=str(vconfig.deepseek_api_key),
            timeout_seconds=int(vconfig.deepseek_timeout_seconds),
            provider_tag="deepseek",
        )
        super().__init__(provider_name="deepseek", client=client)
