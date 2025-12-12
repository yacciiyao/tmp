# -*- coding: utf-8 -*-
# @File: rag_retrieval.py
# @Author: yaccii
# @Time: 2025-12-12 17:25
# @Description:
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set


@dataclass(frozen=True)
class RetrieverHit:
    """
    单一检索器返回的 hit（dense 或 sparse）
    """
    chunk_id: int
    doc_id: int
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    retriever: str = "unknown"  # "dense" | "sparse"


@dataclass(frozen=True)
class FusedHit:
    """
    融合后的 hit（来自 dense/sparse 之一或两者）
    """
    chunk_id: int
    doc_id: int
    score: float  # 融合后的最终排序分（如 RRF 分）
    sources: Set[str] = field(default_factory=set)  # {"dense","sparse"}
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def source_label(self) -> str:
        if "dense" in self.sources and "sparse" in self.sources:
            return "fusion"
        if "dense" in self.sources:
            return "dense"
        if "sparse" in self.sources:
            return "sparse"
        return "fusion"
