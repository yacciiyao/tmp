# -*- coding: utf-8 -*-
# @File: infrastructure/vector_store/faiss_store.py
# @Author: yaccii
# @Description: 基于 FAISS 的向量库实现（单机开发用）

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from infrastructure.vector_store.vector_store_base import ScoredVector, VectorStore

try:
    import faiss  # type: ignore
except ImportError as e:  # pragma: no cover
    faiss = None
    _faiss_import_error = e
else:
    _faiss_import_error = None


@dataclass
class _CorpusIndex:
    """
    每个 corpus 的索引与元数据。
    """
    dim: int
    index: Any  # faiss.Index
    next_vector_id: int
    metas: Dict[int, Dict[str, Any]]  # vector_id -> metadata


class FaissVectorStore(VectorStore):
    """
    简单的 FAISS 向量库实现（内存版）：
    - 针对 demo / 单机开发足够；
    - 支持多 corpus_id；
    - 向量 ID 自增并保存在内存中；
    - 如需持久化，可在此基础上扩展 save/load 逻辑，而不改变接口。
    """

    def __init__(self, use_inner_product: bool = True) -> None:
        if faiss is None:
            raise RuntimeError(
                "FaissVectorStore 需要 faiss 支持，请先安装依赖：`pip install faiss-cpu numpy`"
            ) from _faiss_import_error

        self.use_inner_product = use_inner_product
        self._indices: Dict[int, _CorpusIndex] = {}

    # ---------------------------
    # 内部工具
    # ---------------------------

    def _ensure_index(self, corpus_id: int, dim: int) -> _CorpusIndex:
        if corpus_id in self._indices:
            ci = self._indices[corpus_id]
            if ci.dim != dim:
                raise ValueError(
                    f"Faiss index dim mismatch for corpus {corpus_id}: "
                    f"existing={ci.dim}, new={dim}"
                )
            return ci

        if self.use_inner_product:
            index = faiss.IndexFlatIP(dim)
        else:
            index = faiss.IndexFlatL2(dim)

        ci = _CorpusIndex(
            dim=dim,
            index=index,
            next_vector_id=0,
            metas={},
        )
        self._indices[corpus_id] = ci
        return ci

    @staticmethod
    def _to_f32_matrix(vectors: List[List[float]]) -> np.ndarray:
        return np.asarray(vectors, dtype=np.float32)

    # ---------------------------
    # 对外接口实现
    # ---------------------------

    async def add_embeddings(
        self,
        corpus_id: int,
        doc_id: int,
        chunk_ids: List[int],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> List[int]:
        if not embeddings:
            return []

        if len(chunk_ids) != len(embeddings) or len(chunk_ids) != len(metadatas):
            raise ValueError("chunk_ids / embeddings / metadatas length mismatch")

        dim = len(embeddings[0])
        ci = self._ensure_index(corpus_id, dim)

        vectors = self._to_f32_matrix(embeddings)
        num = vectors.shape[0]

        # 分配 vector_id
        start_id = ci.next_vector_id
        vector_ids = list(range(start_id, start_id + num))
        ci.next_vector_id += num

        # 补充 metadata 中的 corpus_id/doc_id/chunk_id/vector_id
        for i, vid in enumerate(vector_ids):
            meta = dict(metadatas[i] or {})
            meta.setdefault("corpus_id", corpus_id)
            meta.setdefault("doc_id", doc_id)
            meta.setdefault("chunk_id", chunk_ids[i])
            meta["vector_id"] = vid
            ci.metas[vid] = meta

        # FAISS 入库（放到线程池防止阻塞事件循环）
        def _add() -> None:
            ci.index.add(vectors)

        await asyncio.to_thread(_add)

        return vector_ids

    async def search(
        self,
        corpus_id: int,
        query_embedding: List[float],
        top_k: int = 8,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ScoredVector]:
        if corpus_id not in self._indices:
            return []

        ci = self._indices[corpus_id]
        if not ci.index.is_trained or ci.index.ntotal == 0:
            return []

        q = self._to_f32_matrix([query_embedding])

        def _search() -> Tuple[np.ndarray, np.ndarray]:
            # distances: (1, k), ids: (1, k)
            return ci.index.search(q, top_k)

        distances, ids = await asyncio.to_thread(_search)

        results: List[ScoredVector] = []
        for dist, vid in zip(distances[0], ids[0]):
            if vid == -1:
                continue
            meta = ci.metas.get(int(vid), {})
            # 简单过滤：filters 是一个 dict，要求 meta 中的对应字段相等
            if filters:
                ok = True
                for k, v in filters.items():
                    if meta.get(k) != v:
                        ok = False
                        break
                if not ok:
                    continue

            results.append(
                ScoredVector(
                    vector_id=int(vid),
                    score=float(dist),
                    metadata=meta,
                )
            )

        return results
