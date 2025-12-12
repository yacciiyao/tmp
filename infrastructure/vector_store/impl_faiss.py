# -*- coding: utf-8 -*-
# @File: infrastructure/vector_store/impl_faiss.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
from infrastructure import mlogger

try:
    import faiss  # type: ignore
except Exception as e:  # pragma: no cover
    faiss = None

from .base import VectorStore


@dataclass
class _CorpusIndex:
    dim: int
    index: Any
    next_vector_id: int = 0
    metas: Dict[int, Dict[str, Any]] = field(default_factory=dict)


class FaissVectorStore(VectorStore):
    def __init__(self, use_inner_product: bool = True) -> None:
        if faiss is None:
            raise RuntimeError("FaissVectorStore requires faiss-cpu installed.")
        self.use_inner_product = bool(use_inner_product)
        self._corpora: Dict[int, _CorpusIndex] = {}

    # ---------- helpers ----------

    def _ensure_index(self, corpus_id: int, dim: int) -> _CorpusIndex:
        ci = self._corpora.get(corpus_id)
        if ci:
            if ci.dim != dim:
                raise ValueError(f"FAISS dim mismatch: {ci.dim} != {dim} (corpus={corpus_id})")
            return ci

        index = faiss.IndexFlatIP(dim) if self.use_inner_product else faiss.IndexFlatL2(dim)
        ci = _CorpusIndex(dim=dim, index=index)
        self._corpora[cor_id := corpus_id] = ci
        mlogger.info("FaissVectorStore", "create_index", corpus_id=cor_id, dim=dim, ip=self.use_inner_product)
        return ci

    @staticmethod
    def _to_f32_matrix(v: List[List[float]] | List[float]) -> np.ndarray:
        arr = np.array(v, dtype="float32")
        if arr.ndim == 1:  # single vector
            arr = arr.reshape(1, -1)
        return arr

    @staticmethod
    def _l2_normalize(x: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(x, axis=1, keepdims=True) + 1e-12
        return x / norms

    # ---------- API ----------

    async def add_embeddings(
        self,
        *,
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

        X = self._to_f32_matrix(embeddings)
        if self.use_inner_product:
            X = self._l2_normalize(X)

        count = X.shape[0]
        vector_ids = list(range(ci.next_vector_id, ci.next_vector_id + count))
        ci.next_vector_id += count

        await asyncio.to_thread(ci.index.add, X)

        for i, vid in enumerate(vector_ids):
            meta = dict(metadatas[i] or {})
            meta.setdefault("corpus_id", corpus_id)
            meta.setdefault("doc_id", doc_id)
            meta.setdefault("chunk_id", chunk_ids[i])
            meta["vector_id"] = vid
            ci.metas[vid] = meta

        return vector_ids

    async def search(
        self,
        *,
        corpus_id: int,
        query_embedding: List[float],
        top_k: int = 8,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        ci = self._corpora.get(corpus_id)
        if not ci or ci.index.ntotal == 0:
            return []

        q = self._to_f32_matrix(query_embedding)
        if self.use_inner_product:
            q = self._l2_normalize(q)

        D, I = await asyncio.to_thread(ci.index.search, q, top_k)
        ds, ids = D[0].tolist(), I[0].tolist()

        results: List[Dict[str, Any]] = []
        for score, vid in zip(ds, ids):
            if vid == -1:
                continue
            meta = ci.metas.get(vid) or {}
            if filters:
                ok = True
                for k, v in filters.items():
                    if meta.get(k) != v:
                        ok = False
                        break
                if not ok:
                    continue
            results.append(
                {
                    "chunk_id": int(meta.get("chunk_id")),
                    "vector_id": int(vid),
                    "score": float(score),
                    "metadata": meta,
                }
            )
        return results
