# -*- coding: utf-8 -*-
# @File: application/rag/dto.py
# @Author: yaccii
# @Description: RAG 相关 DTO

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


# ====================== Corpus ======================


class CorpusCreateRequest(BaseModel):
    """
    创建知识库请求
    """
    name: str
    type: str = "project"  # project / user / global ...
    description: Optional[str] = None
    owner_id: int = 0

    # 默认使用的 embedding 模型 alias（来自 llm_model.alias）
    default_embedding_alias: str = "openai-embedding"

    # 向量库类型：faiss / milvus / ...
    vector_store_type: str = "faiss"

    # ES 索引名，可为空（由后端按前缀 + corpus_id 生成）
    es_index: Optional[str] = None

    is_active: bool = True


class CorpusUpdateRequest(BaseModel):
    """
    更新知识库请求（部分字段可选）
    """
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    default_embedding_alias: Optional[str] = None
    vector_store_type: Optional[str] = None
    es_index: Optional[str] = None


class CorpusResponse(BaseModel):
    # 允许直接用 ORM 实例来校验
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    description: Optional[str]
    owner_id: int

    default_embedding_alias: Optional[str]
    vector_store_type: str
    es_index: Optional[str]

    is_active: bool
    created_at: int
    updated_at: int


class CorpusListResponse(BaseModel):
    items: List[CorpusResponse]


# ====================== Document ======================


class DocumentCreateRequest(BaseModel):
    """
    创建文档记录（后台上传、URL 导入、文本导入）
    """
    source_type: str = "file"   # file / url / text
    source_uri: str            # 文件路径 / URL / 文本 ID
    file_name: str
    mime_type: str = "text/plain"

    # 额外元信息（页码、上传人、标签等）
    extra_meta: Optional[Dict[str, Any]] = None


class DocumentResponse(BaseModel):
    # 同样允许 `model_validate(orm)`
    model_config = ConfigDict(from_attributes=True)

    id: int
    corpus_id: int
    source_type: str
    source_uri: str
    file_name: Optional[str]
    mime_type: Optional[str]

    status: str
    error_msg: Optional[str]
    num_chunks: Optional[int]
    extra_meta: Optional[Dict[str, Any]]

    created_at: int
    updated_at: int


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]


# ====================== RAG 检索 ======================


class RAGQueryRequest(BaseModel):
    """
    RAG 检索请求：
    - 前台/后台都可以用这个 DTO 调用 RAG 检索服务
    """
    corpus_id: int
    query: str

    top_k: int = 8

    # 是否启用向量检索 / BM25
    use_vector: bool = True
    use_bm25: bool = True

    # 预留：是否启用重排（例如 cross-encoder）
    use_rerank: bool = False


class RAGChunkHit(BaseModel):
    """
    单个命中的 chunk：
    - 携带 chunk/doc/corpus 信息
    - 以及检索打分（融合之后的最终 score）
    """
    chunk_id: int
    doc_id: int
    corpus_id: int

    score: float

    source_type: str
    source_uri: Optional[str] = None

    text: str
    meta: Dict[str, Any] = {}


class RAGQueryResponse(BaseModel):
    """
    RAG 检索响应：
    - hits：命中的 chunk 列表（按 score 排序）
    - context：直接可拼在 Prompt 里的上下文文本（简单拼接）
    """
    corpus_id: int
    query: str
    hits: List[RAGChunkHit]
    context: str
