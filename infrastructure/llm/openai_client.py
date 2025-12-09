# -*- coding: utf-8 -*-
# @File: openai_client.py
# @Author: yaccii
# @Description:
from __future__ import annotations

import os
from typing import AsyncIterator, List, Optional

from openai import AsyncOpenAI

from .llm_base import BaseLLMClient, ChatMessage, LLMCapabilities


class OpenAIClient(BaseLLMClient):
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
        self.alias = alias
        self.model = model
        self.capabilities = capabilities or LLMCapabilities()
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens

        # 若未指定单独的 embedding_model，则默认用同一个 model
        self._embedding_model = embedding_model or model

        # 兜底：如果上层没准备好 api_key/base_url，可以从环境变量取
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY", "")
        if base_url is None:
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    # ---------- 文本对话 ----------

    async def acomplete(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        if not self.capabilities.chat:
            raise RuntimeError(f"Model {self.alias} does not support chat")

        if max_tokens is None and self.max_output_tokens is not None:
            max_tokens = self.max_output_tokens

        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            **kwargs,
        )

        if not resp.choices:
            return ""
        return resp.choices[0].message.content or ""

    async def astream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        if not (self.capabilities.chat and self.capabilities.stream):
            raise RuntimeError(f"Model {self.alias} does not support streaming chat")

        if max_tokens is None and self.max_output_tokens is not None:
            max_tokens = self.max_output_tokens

        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    # ---------- Embeddings ----------

    async def aembed(
        self,
        texts: List[str],
        **kwargs,
    ) -> List[List[float]]:
        if not self.capabilities.embeddings:
            raise RuntimeError(f"Model {self.alias} does not support embeddings")

        resp = await self._client.embeddings.create(
            model=self._embedding_model,
            input=texts,
            **kwargs,
        )
        return [item.embedding for item in resp.data]

    # ---------- 健康检查 ----------

    async def healthcheck(self) -> bool:
        try:
            _ = await self.acomplete(
                messages=[{"role": "user", "content": "ping"}],
                temperature=0.0,
                max_tokens=8,
            )
            return True
        except Exception:
            return False
