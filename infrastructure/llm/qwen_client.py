# -*- coding: utf-8 -*-
# @File: qwen_client.py
# @Author: yaccii
# @Description:
from __future__ import annotations

from typing import Optional

from .llm_base import LLMCapabilities
from .openai_client import OpenAIClient


class QwenClient(OpenAIClient):
    def __init__(
        self,
        alias: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        capabilities: Optional[LLMCapabilities] = None,
        max_input_tokens: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        embedding_model: Optional[str] = None,
    ) -> None:
        super().__init__(
            alias=alias,
            model=model,
            api_key=api_key,
            base_url=base_url,
            capabilities=capabilities,
            max_input_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens,
            embedding_model=embedding_model,
        )
