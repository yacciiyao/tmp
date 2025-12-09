# -*- coding: utf-8 -*-
# @File: llm_base.py
# @Author: yaccii
# @Description:  LLM 统一抽象层

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, List, Optional, TypedDict


class ChatMessage(TypedDict):
    """
    统一对话消息结构：
    - role: "system" / "user" / "assistant"
    - content: 纯文本（图片、语音等额外内容由上层负责转换/拼接）
    """
    role: str
    content: str


@dataclass
class LLMCapabilities:
    """
    模型能力矩阵（由 LLMModelORM 映射而来）：
    - chat / stream / embeddings / rerank
    - vision: 图文理解
    - image: 文生图
    - audio_stt: 语音转文本
    - audio_tts: 文本转语音
    """
    chat: bool = True
    stream: bool = True
    embeddings: bool = False
    rerank: bool = False
    vision: bool = False
    image: bool = False
    audio_stt: bool = False
    audio_tts: bool = False


class BaseLLMClient:
    """
    所有具体 LLM 客户端的统一接口。
    只做“调大模型”这件事，不关心 RAG / Agent / 多模态业务流程。
    """

    alias: str
    model: str
    capabilities: LLMCapabilities
    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None

    # ---------- 文本对话 ----------

    async def acomplete(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        非流式对话，返回完整文本。
        """
        raise NotImplementedError

    async def astream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        流式对话，yield 文本增量。
        """
        raise NotImplementedError

    # ---------- 文本向量（RAG 用） ----------

    async def aembed(
        self,
        texts: List[str],
        **kwargs,
    ) -> List[List[float]]:
        """
        文本 embedding。
        只在 capabilities.embeddings=True 时使用。
        """
        raise NotImplementedError

    # ---------- 健康检查 ----------

    async def healthcheck(self) -> bool:
        """
        探活接口，用于监控/启动诊断。
        """
        raise NotImplementedError
