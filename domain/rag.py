# -*- coding: utf-8 -*-
# @File: rag.py
# @Author: yaccii
# @Description:
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RAGCorpus:
    id: int
    name: str
    type: str  # project / brand / global / custom
    description: Optional[str] = None
    owner_id: Optional[int] = None

    default_embedding_alias: Optional[str] = None
    vector_store_type: Optional[str] = None
    es_index: Optional[str] = None

    is_active: bool = True

    created_at: Optional[int] = None
    updated_at: Optional[int] = None


@dataclass
class RAGDocument:
    id: int
    corpus_id: int

    source_type: str      # file / url / text
    source_uri: str

    file_name: Optional[str] = None
    mime_type: Optional[str] = None

    status: str = "pending"     # pending / processing / ready / failed
    error_msg: Optional[str] = None

    num_chunks: Optional[int] = None
    extra_meta: Optional[Dict[str, Any]] = None

    created_at: Optional[int] = None
    updated_at: Optional[int] = None


@dataclass
class RAGChunk:
    id: int
    corpus_id: int
    doc_id: int

    chunk_index: int
    text: str

    meta: Optional[Dict[str, Any]] = None
    vector_id: Optional[int] = None

    created_at: Optional[int] = None
    updated_at: Optional[int] = None


@dataclass
class RetrievedChunk:
    chunk: RAGChunk
    score: float
    rank: Optional[int] = None
    source: Optional[str] = None  # dense / sparse / fusion 等标签


@dataclass
class RAGAnswer:
    answer: str
    query: str
    corpus_ids: List[int]

    contexts: List[RetrievedChunk]
    model_alias: str

    raw_prompt: Optional[str] = None
    debug_info: Optional[Dict[str, Any]] = None
