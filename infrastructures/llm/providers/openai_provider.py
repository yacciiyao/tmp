# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: OpenAI provider adapter.

from __future__ import annotations

from infrastructures.llm.clients.openai_compatible_client import OpenAICompatibleClient
from infrastructures.llm.providers.openai_compatible_provider_base import OpenAICompatibleProviderBase
from infrastructures.vconfig import vconfig


class OpenAIProvider(OpenAICompatibleProviderBase):
    """OpenAI provider.

    Default mode: OpenAI-compatible /v1/chat/completions.
    If you later need OpenAI Responses API or Realtime, add a separate native adapter
    and select it via model profile meta (api_style) at the execution layer.
    """

    def __init__(self) -> None:
        client = OpenAICompatibleClient(
            base_url=str(vconfig.openai_base_url),
            api_key=str(vconfig.openai_api_key),
            timeout_seconds=int(vconfig.openai_timeout_seconds),
            provider_tag="openai",
        )
        super().__init__(provider_name="openai", client=client)
