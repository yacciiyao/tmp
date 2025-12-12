# -*- coding: utf-8 -*-
# @File: normalizers.py
# @Author: yaccii
# @Time: 2025-12-12 17:26
# @Description:
from __future__ import annotations

from typing import Any, Dict, List

from domain.rag_retrieval import RetrieverHit


def normalize_dense_hits(raw: List[Dict[str, Any]]) -> List[RetrieverHit]:
    """
    兼容 vector_store.search 的返回结构：
    - chunk_id 可能在顶层或 metadata
    - doc_id 通常在 metadata["doc_id"]
    """
    out: List[RetrieverHit] = []
    for h in raw or []:
        meta = h.get("metadata") or {}
        chunk_id = int(h.get("chunk_id") or meta.get("chunk_id") or 0)
        doc_id = int(meta.get("doc_id") or h.get("doc_id") or 0)
        if chunk_id <= 0 or doc_id <= 0:
            continue
        out.append(
            RetrieverHit(
                chunk_id=chunk_id,
                doc_id=doc_id,
                score=float(h.get("score", 0.0)),
                metadata=meta,
                retriever="dense",
            )
        )
    return out


def normalize_sparse_hits(raw: List[Dict[str, Any]]) -> List[RetrieverHit]:
    """
    兼容 ESClient.search 的统一返回（你上一轮已改成统一 dict schema）：
    {"chunk_id","doc_id","score","metadata"}
    也兼容旧实现可能的 meta/metadata 字段。
    """
    out: List[RetrieverHit] = []
    for h in raw or []:
        meta = h.get("metadata") or h.get("meta") or {}
        chunk_id = int(h.get("chunk_id") or meta.get("chunk_id") or 0)
        doc_id = int(h.get("doc_id") or meta.get("doc_id") or 0)
        if chunk_id <= 0 or doc_id <= 0:
            continue
        out.append(
            RetrieverHit(
                chunk_id=chunk_id,
                doc_id=doc_id,
                score=float(h.get("score", 0.0)),
                metadata=meta,
                retriever="sparse",
            )
        )
    return out
