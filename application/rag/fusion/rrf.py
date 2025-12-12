# -*- coding: utf-8 -*-
# @File: rrf.py
# @Author: yaccii
# @Time: 2025-12-12 17:27
# @Description:
from __future__ import annotations

from typing import Dict, List

from application.rag.fusion.base import FusionStrategy
from domain.rag_retrieval import FusedHit, RetrieverHit


class RRFFusionStrategy(FusionStrategy):
    """
    Reciprocal Rank Fusion:
    score = sum(1 / (k + rank))
    输入列表的顺序即 rank 顺序（第 1 个 rank=1）
    """

    def __init__(self, k: float = 60.0) -> None:
        self.k = float(k)

    def fuse(self, dense: List[RetrieverHit], sparse: List[RetrieverHit], top_k: int) -> List[FusedHit]:
        merged: Dict[int, Dict] = {}  # chunk_id -> agg dict

        def add(hits: List[RetrieverHit], src: str) -> None:
            for rank, h in enumerate(hits, start=1):
                if h.chunk_id <= 0 or h.doc_id <= 0:
                    continue
                rrf = 1.0 / (self.k + rank)

                if h.chunk_id not in merged:
                    merged[h.chunk_id] = {
                        "chunk_id": h.chunk_id,
                        "doc_id": h.doc_id,
                        "rrf": 0.0,
                        "sources": set(),
                        "dense_score": None,
                        "sparse_score": None,
                        "metadata": h.metadata or {},
                    }

                merged[h.chunk_id]["rrf"] += rrf
                merged[h.chunk_id]["sources"].add(src)

                if src == "dense":
                    merged[h.chunk_id]["dense_score"] = h.score
                elif src == "sparse":
                    merged[h.chunk_id]["sparse_score"] = h.score

                # metadata 合并策略：以首次出现为主；如需更复杂（合并字段）可扩展
                if not merged[h.chunk_id].get("metadata") and h.metadata:
                    merged[h.chunk_id]["metadata"] = h.metadata

        add(dense, "dense")
        add(sparse, "sparse")

        fused = [
            FusedHit(
                chunk_id=v["chunk_id"],
                doc_id=v["doc_id"],
                score=float(v["rrf"]),
                sources=set(v["sources"]),
                dense_score=v.get("dense_score"),
                sparse_score=v.get("sparse_score"),
                metadata=v.get("metadata") or {},
            )
            for v in merged.values()
        ]

        fused.sort(key=lambda x: x.score, reverse=True)
        return fused[: int(top_k)]
