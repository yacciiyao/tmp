# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: LLM HTTP/SDK clients (infrastructure only).

from infrastructures.llm.clients.openai_compatible_client import OpenAICompatibleClient
from infrastructures.llm.clients.ollama_native_client import OllamaNativeClient

__all__ = [
    "OpenAICompatibleClient",
    "OllamaNativeClient",
]
