# -*- coding: utf-8 -*-
# @File: infrastructure/llm/gemini_client.py
# @Author: yaccii
# @Description: Gemini 客户端（只支持非流式）

from __future__ import annotations

import asyncio
from typing import AsyncIterator, List, Optional

from google import genai
from google.genai import types

from .llm_base import BaseLLMClient, ChatMessage, LLMCapabilities


class GeminiClient(BaseLLMClient):
    """
    Gemini 客户端：

    - 只支持非流式 acomplete；
    - astream 明确不支持（直接抛异常），避免半吊子行为。
    """

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
        self._model_id = model if model.startswith("models/") else f"models/{model}"

        self.capabilities = capabilities or LLMCapabilities()
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self._embedding_model = embedding_model

        if not api_key:
            raise RuntimeError("GeminiClient requires api_key")

        http_options = types.HttpOptions(base_url=base_url) if base_url else None

        self._client = genai.Client(
            api_key=api_key,
            http_options=http_options,
        )

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _to_prompt(messages: List[ChatMessage]) -> str:
        """
        role: content
        ...
        assistant:
        """
        lines: List[str] = []
        for m in messages:
            role = (m["role"] or "user").strip()
            content = (m["content"] or "").strip()
            if not content:
                continue
            lines.append(f"{role}: {content}")
        lines.append("assistant:")
        return "\n".join(lines)

    def _build_config(
        self,
        temperature: float,
        max_tokens: Optional[int],
    ) -> types.GenerateContentConfig:
        if max_tokens is None and self.max_output_tokens is not None:
            max_tokens = self.max_output_tokens

        return types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    @staticmethod
    def _extract_text_from_response(resp) -> str:
        # 1) 直接有 text 字段
        if getattr(resp, "text", None):
            return resp.text.strip()

        # 2) 从 candidates 里拿
        if getattr(resp, "candidates", None):
            cand = resp.candidates[0]

            parts = getattr(cand, "parts", None)
            if parts is None and getattr(cand, "content", None):
                parts = getattr(cand.content, "parts", []) or []

            if parts:
                chunks = [getattr(p, "text", "") or "" for p in parts]
                return "".join(chunks).strip()

        return ""

    # ------------------------------------------------------------------
    # 非流式：完整回复
    # ------------------------------------------------------------------

    async def acomplete(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.0,
        max_tokens: Optional[int] = 128,
        **kwargs,
    ) -> str:
        if not self.capabilities.chat:
            raise RuntimeError(f"Model {self.alias} does not support chat")

        prompt = self._to_prompt(messages)
        cfg = self._build_config(temperature=temperature, max_tokens=max_tokens)

        def _call() -> str:
            resp = self._client.models.generate_content(
                model=self._model_id,
                contents=prompt,
                config=cfg,
                **kwargs,
            )
            return self._extract_text_from_response(resp)

        # 同步 SDK 丢线程池，避免阻塞事件循环
        return await asyncio.wait_for(asyncio.to_thread(_call), timeout=30)

    # ------------------------------------------------------------------
    # 流式：明确不支持
    # ------------------------------------------------------------------

    async def astream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.0,
        max_tokens: Optional[int] = 128,
        **kwargs,
    ) -> AsyncIterator[str]:
        raise RuntimeError("GeminiClient does not support streaming (astream disabled)")

    # ------------------------------------------------------------------
    # Embedding（占位）
    # ------------------------------------------------------------------

    async def aembed(
        self,
        texts: List[str],
        **kwargs,
    ) -> List[List[float]]:
        if not self.capabilities.embeddings:
            raise RuntimeError(f"Model {self.alias} does not support embeddings")
        raise NotImplementedError("Gemini embeddings are not implemented")

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    async def healthcheck(self) -> bool:
        try:
            _ = await self.acomplete(
                messages=[{"role": "user", "content": "ping"}],
                temperature=0.0,
                max_tokens=16,
            )
            return True
        except Exception:
            return False
