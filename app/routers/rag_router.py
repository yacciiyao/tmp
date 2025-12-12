# -*- coding: utf-8 -*-
# @File: app/routers/rag_router.py
# @Author: yaccii
# @Description: RAG 管理与调试接口

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.auth import get_current_admin, get_current_user
from application.rag.dto import (
    CorpusCreateRequest,
    CorpusUpdateRequest,
    CorpusResponse,
    CorpusListResponse,
    DocumentCreateRequest,
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGDeleteResponse,
)
from application.rag.rag_service import RAGService
from application.rag.ingestion_service import IngestionService, IngestionResult
from domain.user import UserPublic
from infrastructure.db.deps import get_db

router = APIRouter(prefix="/rag", tags=["rag"])


# ====================== Service 依赖 ======================

def get_rag_service(db: AsyncSession = Depends(get_db)) -> RAGService:
    return RAGService(db)

def get_ingestion_service(db: AsyncSession = Depends(get_db)) -> IngestionService:
    return IngestionService(db)


# ====================== 知识库（Corpus）相关 ======================

@router.post("/corpora", response_model=CorpusResponse)
async def create_corpus(
    req: CorpusCreateRequest,
    svc: RAGService = Depends(get_rag_service),
    current_admin: UserPublic = Depends(get_current_admin),
) -> CorpusResponse:
    """
    创建知识库（仅管理员）。
    owner_id 取当前管理员 id。
    """
    return await svc.create_corpus(req, owner_id=current_admin.id)

@router.get("/corpora", response_model=CorpusListResponse)
async def list_corpora(
    owner_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    svc: RAGService = Depends(get_rag_service),
    current_admin: UserPublic = Depends(get_current_admin),
) -> CorpusListResponse:
    """
    列出知识库（仅管理员），可按 owner_id 过滤。
    """
    return await svc.list_corpora(owner_id=owner_id, limit=limit, offset=offset, active_only=True)

@router.get("/corpora/{corpus_id}", response_model=CorpusResponse)
async def get_corpus(
    corpus_id: int,
    svc: RAGService = Depends(get_rag_service),
    current_admin: UserPublic = Depends(get_current_admin),
) -> CorpusResponse:
    """
    获取单个知识库详情（仅管理员）。
    """
    try:
        return await svc.get_corpus(corpus_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/corpora/{corpus_id}", response_model=CorpusResponse)
async def update_corpus(
    corpus_id: int,
    req: CorpusUpdateRequest,
    svc: RAGService = Depends(get_rag_service),
    current_admin: UserPublic = Depends(get_current_admin),
) -> CorpusResponse:
    """
    更新知识库信息（仅管理员）。
    """
    try:
        return await svc.update_corpus(corpus_id, req)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/corpora/{corpus_id}", response_model=RAGDeleteResponse)
async def delete_corpus(
    corpus_id: int,
    svc: RAGService = Depends(get_rag_service),
    current_admin: UserPublic = Depends(get_current_admin),
) -> RAGDeleteResponse:
    """
    删除（软删）知识库（仅管理员）。
    """
    try:
        data = await svc.delete_corpus(corpus_id)
        return RAGDeleteResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ====================== 文档（Document）相关 ======================

@router.post("/corpora/{corpus_id}/documents", response_model=DocumentResponse)
async def create_document(
    corpus_id: int,
    req: DocumentCreateRequest,
    svc: RAGService = Depends(get_rag_service),
    current_admin: UserPublic = Depends(get_current_admin),
) -> DocumentResponse:
    """
    创建文档记录（仅管理员）。只登记来源，不做解析与入库。
    如果 (file_name/source_uri) 与现有文档重复，自动软删旧版本。
    """
    return await svc.create_document(corpus_id=corpus_id, req=req, uploader_id=current_admin.id)

@router.get("/corpora/{corpus_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    corpus_id: int,
    limit: int = 100,
    offset: int = 0,
    svc: RAGService = Depends(get_rag_service),
    current_admin: UserPublic = Depends(get_current_admin),
) -> DocumentListResponse:
    """
    列出某个知识库下的文档（仅管理员）。
    """
    return await svc.list_documents(corpus_id=corpus_id, limit=limit, offset=offset)

@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    svc: RAGService = Depends(get_rag_service),
    current_admin: UserPublic = Depends(get_current_admin),
) -> DocumentResponse:
    """
    获取单个文档详情（仅管理员）。
    """
    try:
        return await svc.get_document(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/documents/{doc_id}", response_model=RAGDeleteResponse)
async def delete_document(
    doc_id: int,
    svc: RAGService = Depends(get_rag_service),
    current_admin: UserPublic = Depends(get_current_admin),
) -> RAGDeleteResponse:
    """
    删除（软删）文档（仅管理员）。
    """
    try:
        data = await svc.delete_document(doc_id)
        return RAGDeleteResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ====================== 入库（Ingestion）相关 ======================

@router.post("/corpora/{corpus_id}/upload_and_ingest", response_model=DocumentUploadResponse)
async def upload_and_ingest_document(
    corpus_id: int,
    file: UploadFile = File(...),
    svc: RAGService = Depends(get_rag_service),
    current_admin: UserPublic = Depends(get_current_admin),
) -> DocumentUploadResponse:
    """
    一步式上传并入库（仅管理员）：
    - 上传文件到本地/S3（由配置决定）
    - 创建 Document（若重复会软删旧版本）
    - 执行入库：解析/切分/向量化/ES 索引
    - 返回 Document + 文件相对路径/URL
    """
    return await svc.upload_and_ingest_document(
        corpus_id=corpus_id,
        uploader_id=current_admin.id,
        upload=file,
    )

@router.post("/documents/{doc_id}/ingest", response_model=IngestionResult)
async def ingest_document(
    doc_id: int,
    ingestion_svc: IngestionService = Depends(get_ingestion_service),
    current_admin: UserPublic = Depends(get_current_admin),
) -> IngestionResult:
    """
    触发指定文档的 RAG 入库（仅管理员）：
    - 解析 / 切分
    - 向量化
    - 写入向量库 / ES
    - 更新文档状态
    """
    return await ingestion_svc.ingest_document(doc_id=doc_id)


# ====================== 检索（Query）相关 ======================

@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(
    req: RAGQueryRequest,
    svc: RAGService = Depends(get_rag_service),
    current_user: UserPublic = Depends(get_current_user),
) -> RAGQueryResponse:
    """
    调试/对话用 RAG 检索接口（普通用户可用）：
    - 输入 corpus_id + query
    - 返回融合后的命中 + 拼接 context_text
    - 命中项包含数据源信息（source_type/source_uri/source_url）
    """
    return await svc.query(req)
