# -*- coding: utf-8 -*-
# @File: app/routers/rag_router.py
# @Author: yaccii
# @Description: RAG 管理与调试接口（后台使用）

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from application.rag.dto import (
    CorpusCreateRequest,
    CorpusResponse,
    CorpusListResponse,
    DocumentCreateRequest,
    DocumentResponse,
    DocumentListResponse,
    RAGQueryRequest,
    RAGQueryResponse
)
from application.rag.rag_service import RAGService
from application.rag.ingestion_service import IngestionService, IngestionResult
from application.rag.query_service import RAGQueryService
from infrastructure.db.deps import get_db

router = APIRouter(prefix="/rag", tags=["rag"])


# ====================== Service 依赖 ======================


def get_rag_service(db: AsyncSession = Depends(get_db)) -> RAGService:
    return RAGService(db)


def get_ingestion_service(db: AsyncSession = Depends(get_db)) -> IngestionService:
    return IngestionService(db)


def get_rag_query_service(db: AsyncSession = Depends(get_db)) -> RAGQueryService:
    return RAGQueryService(db)


# ====================== 知识库（Corpus）相关 ======================


@router.post("/corpora", response_model=CorpusResponse)
async def create_corpus(
    req: CorpusCreateRequest,
    svc: RAGService = Depends(get_rag_service),
) -> CorpusResponse:
    """
    创建知识库（后台管理使用）。
    """
    return await svc.create_corpus(req)


@router.get("/corpora", response_model=CorpusListResponse)
async def list_corpora(
    owner_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    svc: RAGService = Depends(get_rag_service),
) -> CorpusListResponse:
    """
    列出知识库，可按 owner_id 过滤。
    """
    return await svc.list_corpora(owner_id=owner_id, limit=limit, offset=offset)


@router.get("/corpora/{corpus_id}", response_model=CorpusResponse)
async def get_corpus(
    corpus_id: int,
    svc: RAGService = Depends(get_rag_service),
) -> CorpusResponse:
    """
    获取单个知识库详情。
    """
    try:
        return await svc.get_corpus(corpus_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ====================== 文档（Document）相关 ======================


@router.post("/corpora/{corpus_id}/documents", response_model=DocumentResponse)
async def create_document(
    corpus_id: int,
    req: DocumentCreateRequest,
    svc: RAGService = Depends(get_rag_service),
) -> DocumentResponse:
    """
    创建文档记录（只登记来源信息，不做解析与入库）。

    真正的文件上传建议走独立的 file_router：
    - 先上传文件得到 file_path
    - 再调用本接口，把 file_path 填入 source_uri
    - 最后通过 /rag/documents/{doc_id}/ingest 触发入库
    """
    return await svc.create_document(corpus_id=corpus_id, req=req)


@router.get("/corpora/{corpus_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    corpus_id: int,
    limit: int = 100,
    offset: int = 0,
    svc: RAGService = Depends(get_rag_service),
) -> DocumentListResponse:
    """
    列出某个知识库下的文档。
    """
    return await svc.list_documents(corpus_id=corpus_id, limit=limit, offset=offset)


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    svc: RAGService = Depends(get_rag_service),
) -> DocumentResponse:
    """
    获取单个文档详情。
    """
    try:
        return await svc.get_document(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ====================== 入库（Ingestion）相关 ======================


@router.post("/documents/{doc_id}/ingest", response_model=IngestionResult)
async def ingest_document(
    doc_id: int,
    ingestion_svc: IngestionService = Depends(get_ingestion_service),
) -> IngestionResult:
    """
    触发单个文档的 RAG 入库流程：
    - 解析 / 切分
    - 向量化
    - 写入向量库 / ES
    - 更新文档状态
    """
    # 这里不做业务逻辑判断，异常直接由 FastAPI 统一处理或抛出 500
    return await ingestion_svc.ingest_document(doc_id=doc_id)


# ====================== 检索（Query）相关 ======================


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(
    req: RAGQueryRequest,
    svc: RAGQueryService = Depends(get_rag_query_service),
) -> RAGQueryResponse:
    """
    调试用 RAG 检索接口：
    - 输入 corpus_id + query
    - 返回 context + 命中详情
    """
    return await svc.query(req)
