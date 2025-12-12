# -*- coding: utf-8 -*-
# @File: infrastructure/rag/embeddings.py
# @Description: EmbeddingEngine 薄封装（统一 aembed 调用）

from __future__ import annotations

from typing import List, Protocol


class SupportsEmbedding(Protocol):
    async def aembed(self, texts: List[str]) -> List[List[float]]: ...
    # 仅需 aembed，是否还支持 chat/stream 由具体 client 决定


class EmbeddingEngine:
    def __init__(self, client: SupportsEmbedding) -> None:
        self.client = client

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return await self.client.aembed(texts)

    async def embed_query(self, text: str) -> List[float]:
        if not text:
            return []
        vecs = await self.client.aembed([text])
        return vecs[0] if vecs else []
