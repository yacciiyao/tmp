# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import List

from sentence_transformers import SentenceTransformer


class SentenceTransformerEmbedder:
    """真实 embedding 实现 (使用 SentenceTransformers)"""

    def __init__(self, model_name: str, dim: int | None = None):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dim = dim or self.model.get_sentence_embedding_dimension()

    async def embed_query(self, text: str) -> List[float]:
        emb = self.model.encode([text], normalize_embeddings=True)[0]
        return emb.tolist()

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embs = self.model.encode(texts, normalize_embeddings=True)
        return [e.tolist() for e in embs]
