# -*- coding: utf-8 -*-
# @File: infrastructure/vector_store/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class ScoredVector:
    vector_id: int
    score: float
    metadata: Dict[str, Any]


class VectorStore(Protocol):
    """
    约定：score 越大越相似；filters 为等值过滤（服务端过滤）。
    """

    async def add_embeddings(
        self,
        *,
        corpus_id: int,
        doc_id: int,
        chunk_ids: List[int],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> List[int]:
        ...

    async def search(
        self,
        *,
        corpus_id: int,
        query_embedding: List[float],
        top_k: int = 8,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        返回统一结构：
        [
          {"chunk_id": int, "vector_id": int, "score": float, "metadata": {...}},
          ...
        ]
        """
        ...
