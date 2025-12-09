# -*- coding: utf-8 -*-
# @File: claude_client.py
# @Author: yaccii
# @Description:
from __future__ import annotations

from typing import AsyncIterator, List, Optional

from anthropic import AsyncAnthropic

from .llm_base import BaseLLMClient, ChatMessage, LLMCapabilities


class ClaudeClient(BaseLLMClient):
    def __init__(
        self,
        alias: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        capabilities: Optional[LLMCapabilities] = None,
        max_input_tokens: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        embedding_model: Optional[str] = None,  # 预留
    ) -> None:
        self.alias = alias
        self.model = model
        self.capabilities = capabilities or LLMCapabilities()
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self._embedding_model = embedding_model

        client_kwargs = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url

        self._client = AsyncAnthropic(**client_kwargs)

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
        if max_tokens is None:
            max_tokens = 512

        system = ""
        conv: List[dict] = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            if role == "system":
                system += content + "\n"
            else:
                conv.append({"role": role, "content": content})

        resp = await self._client.messages.create(
            model=self.model,
            system=system or None,
            messages=conv,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        texts: List[str] = []
        for block in resp.content:
            if block.type == "text":
                texts.append(block.text)
        return "".join(texts)

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
        if max_tokens is None:
            max_tokens = 512

        system = ""
        conv: List[dict] = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            if role == "system":
                system += content + "\n"
            else:
                conv.append({"role": role, "content": content})

        stream = await self._client.messages.create(
            model=self.model,
            system=system or None,
            messages=conv,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        async for event in stream:
            # 仅对文本增量做处理
            if event.type == "content_block_delta" and event.delta.type == "text_delta":
                if event.delta.text:
                    yield event.delta.text

    async def aembed(
        self,
        texts: List[str],
        **kwargs,
    ) -> List[List[float]]:
        if not self.capabilities.embeddings:
            raise RuntimeError(f"Model {self.alias} does not support embeddings")
        # 如果未来 Anthropic 开放 embedding，可以在这里实现
        raise NotImplementedError("Claude embeddings are not implemented")

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
