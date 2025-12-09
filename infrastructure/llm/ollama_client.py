# -*- coding: utf-8 -*-
# @File: ollama_client.py
# @Author: yaccii
# @Description:
from __future__ import annotations

import json
import os
from typing import AsyncIterator, List, Optional

import httpx

from .llm_base import BaseLLMClient, ChatMessage, LLMCapabilities


class OllamaClient(BaseLLMClient):
    """
    本地 Ollama：
    - /api/chat: 支持流式 / 非流式
    - /api/tags: 检测服务可用性
    """

    def __init__(
        self,
        alias: str,
        model: str,
        api_key: Optional[str] = None,  # 占位，Ollama 一般不需要
        base_url: Optional[str] = None,
        capabilities: Optional[LLMCapabilities] = None,
        max_input_tokens: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        embedding_model: Optional[str] = None,  # 如需 Ollama embedding 可单独实现
    ) -> None:
        self.alias = alias
        self.model = model
        self.capabilities = capabilities or LLMCapabilities()
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self._embedding_model = embedding_model

        base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self._client = httpx.AsyncClient(base_url=base_url, timeout=60.0)

    async def acomplete(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        if not self.capabilities.chat:
            raise RuntimeError(f"Model {self.alias} does not support chat")

        options = {"temperature": temperature}
        if max_tokens is None and self.max_output_tokens is not None:
            max_tokens = self.max_output_tokens
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": options,
        }

        resp = await self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("message") or {}
        return msg.get("content", "")

    async def astream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        if not (self.capabilities.chat and self.capabilities.stream):
            raise RuntimeError(f"Model {self.alias} does not support streaming chat")

        options = {"temperature": temperature}
        if max_tokens is None and self.max_output_tokens is not None:
            max_tokens = self.max_output_tokens
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": options,
        }

        async with self._client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Ollama 流式响应结构：
                # { "message": { "role": "assistant", "content": "..." }, "done": false }
                msg = data.get("message") or {}
                content = msg.get("content")
                if content:
                    yield content

    async def aembed(
        self,
        texts: List[str],
        **kwargs,
    ) -> List[List[float]]:
        if not self.capabilities.embeddings:
            raise RuntimeError(f"Model {self.alias} does not support embeddings")
        # 如需 Ollama embedding，可对 /api/embeddings 实现
        raise NotImplementedError("Ollama embeddings are not implemented")

    async def healthcheck(self) -> bool:
        try:
            resp = await self._client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False
