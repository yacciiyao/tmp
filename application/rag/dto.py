# -*- coding: utf-8 -*-
# @File: application/rag/dto.py
# @Description: RAG 统一 DTO（与现有 query_service / chat_service 对齐）

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


# ----------------------------------------
# 基础枚举
# ----------------------------------------
class RAGDocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


# ----------------------------------------
# Corpus DTO
# ----------------------------------------
class CorpusCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    default_embedding_alias: Optional[str] = None
    vector_store_type: Optional[str] = None
    es_index: Optional[str] = None


class CorpusUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    default_embedding_alias: Optional[str] = None
    vector_store_type: Optional[str] = None
    es_index: Optional[str] = None
    is_active: Optional[bool] = None


class CorpusResponse(BaseModel):
    id: int
    name: str
    type: str
    description: Optional[str]
    owner_id: int
    default_embedding_alias: Optional[str]
    vector_store_type: Optional[str]
    es_index: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class CorpusListResponse(BaseModel):
    items: List[CorpusResponse] = Field(default_factory=list)


# ----------------------------------------
# Document DTO
# ----------------------------------------
class DocumentCreateRequest(BaseModel):
    """
    后台创建文档记录（仅登记来源，不含上传）：
    - source_type: file/url/text
    - source_uri:
        * file: 传文件相对路径或 S3 key（由文件存储返回的 rel_path/key）
        * url:  直接传 URL
        * text: 直接传文本（可放在 extra_meta["text"]）
    """
    source_type: str = Field(pattern="^(file|url|text)$")
    source_uri: str
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    extra_meta: Optional[Dict[str, Any]] = None
    owner_id: Optional[int] = None  # 记录归属管理员（与 Corpus.owner_id 同维度）


class DocumentResponse(BaseModel):
    id: int
    corpus_id: int
    file_name: Optional[str]
    mime_type: Optional[str]
    owner_id: Optional[int] = None
    uploader_id: Optional[int] = None
    status: RAGDocumentStatus
    num_chunks: int
    error_msg: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse] = Field(default_factory=list)


# ----------------------------------------
# Chunk DTO（后台/调试可用）
# ----------------------------------------
class RAGChunkResponse(BaseModel):
    id: int
    doc_id: int
    chunk_index: int
    text: str
    vector_id: Optional[int]

    class Config:
        from_attributes = True


# ----------------------------------------
# Query / Answer DTO
# ----------------------------------------
class RAGChunkHit(BaseModel):
    chunk_id: int
    doc_id: int
    corpus_id: int
    score: float
    text: str
    # 数据源信息（用于前端展示来源）
    source_type: Optional[str] = None
    source_uri: Optional[str] = None
    source_url: Optional[str] = None  # 通过 file_base_url 拼出来的可访问 URL（file 类型）
    # 命中来源标签（dense/sparse/fusion），query_service 可不填
    source: Optional[str] = None
    # 透传 meta（如页面号、段落位置信息等）
    meta: Optional[Dict[str, Any]] = None


class RAGQueryRequest(BaseModel):
    """
    与现有 query_service / chat_service 对齐（单 corpus 查询）；
    若需多 corpus，可在上层循环或后续扩展。
    """
    corpus_id: int
    query: str
    top_k: int = 8
    use_vector: bool = True
    use_bm25: bool = True
    use_rerank: bool = False  # 先默认 False，保持性能与稳定性


class RAGQueryResponse(BaseModel):
    query: str
    corpus_ids: List[int]
    hits: List[RAGChunkHit]
    context_text: str


# ----------------------------------------
# 上传响应 / 删除响应
# ----------------------------------------
class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    rel_path: str
    file_url: str


class RAGDeleteResponse(BaseModel):
    id: int
    deleted: bool = True
