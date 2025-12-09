# -*- coding: utf-8 -*-
# @File: infrastructure/rag/embeddings.py
# @Author: yaccii
# @Description: Embedding 引擎包装（只定义协议与薄封装）

from __future__ import annotations

from typing import List, Protocol


class SupportsEmbedding(Protocol):
    """
    任意 Embedding Client 只要实现 aembed，就可以被 EmbeddingEngine 使用。
    约定:
    - aembed 接收 texts: List[str]
    - 返回与 texts 一一对应的向量 List[List[float]]
    """

    async def aembed(self, texts: List[str]) -> List[List[float]]:
        ...


class EmbeddingEngine:
    """
    RAG 使用的统一 Embedding 引擎封装：
    - 不关心底层是 OpenAI / DeepSeek / Qwen / 本地模型
    - 不关心参数、base_url 等细节，只要 aembed 可用
    - 上层 Ingestion / Query 只跟 EmbeddingEngine 打交道
    """

    def __init__(self, client: SupportsEmbedding) -> None:
        self._client = client

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        用于文档批量向量化。
        - 保证长度与输入 texts 一致。
        """
        if not texts:
            return []
        return await self._client.aembed(texts)

    async def embed_query(self, text: str) -> List[float]:
        """
        用于查询向量化。
        """
        if not text:
            raise ValueError("query text is empty")

        vectors = await self._client.aembed([text])
        if not vectors or not vectors[0]:
            raise RuntimeError("embedding engine returned empty vector")
        return vectors[0]
