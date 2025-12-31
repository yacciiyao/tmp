# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Gemini provider adapter.

from __future__ import annotations

from infrastructures.llm.clients.openai_compatible_client import OpenAICompatibleClient
from infrastructures.llm.providers.openai_compatible_provider_base import OpenAICompatibleProviderBase
from infrastructures.vconfig import vconfig


class GeminiProvider(OpenAICompatibleProviderBase):
    """Gemini provider.

    This project treats Gemini as an OpenAI-compatible gateway by default.
    If you want to call Google native Gemini API later, add a separate native adapter.
    """

    def __init__(self) -> None:
        client = OpenAICompatibleClient(
            base_url=str(vconfig.gemini_base_url),
            api_key=str(vconfig.gemini_api_key),
            timeout_seconds=int(vconfig.gemini_timeout_seconds),
            provider_tag="gemini",
        )
        super().__init__(provider_name="gemini", client=client)
