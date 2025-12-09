# -*- coding: utf-8 -*-
# @File: infrastructure/vector_store/vector_store_base.py
# @Author: yaccii
# @Description: 向量库抽象基类和通用结构

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class ScoredVector:
    """
    向量检索返回结构：
    - vector_id: 向量在向量库中的内部 ID（由具体实现决定）
    - score: 相似度分数（通常越大越相似，具体实现可用 inner-product / cosine 等）
    - metadata: 任意与该向量关联的元信息（chunk_id / corpus_id / doc_id 等）
    """
    vector_id: int
    score: float
    metadata: Dict[str, Any]


class VectorStore(Protocol):
    """
    向量库统一接口。

    约定：
    - 支持多 corpus_id（一个向量库实例可管理多个知识库）。
    - embeddings 维度由具体实现维护，不要求外部知道。
    """

    async def add_embeddings(
        self,
        corpus_id: int,
        doc_id: int,
        chunk_ids: List[int],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> List[int]:
        """
        添加一批向量，返回每个向量对应的 vector_id 列表（与 chunk_ids 一一对应）。
        - corpus_id: 知识库 ID
        - doc_id: 文档 ID
        - chunk_ids: rag_chunk.id 列表
        - embeddings: 向量列表
        - metadatas: 与每个向量对应的元信息（会至少包含 chunk_id/doc_id/corpus_id）
        """
        ...

    async def search(
        self,
        corpus_id: int,
        query_embedding: List[float],
        top_k: int = 8,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ScoredVector]:
        """
        在指定 corpus 中做向量检索。
        - filters: 预留过滤条件（如 doc_id 范围、标签等），具体实现可选择支持/忽略。
        """
        ...
