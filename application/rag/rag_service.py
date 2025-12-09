# -*- coding: utf-8 -*-
# @File: application/rag/rag_service.py
# @Author: yaccii
# @Description: RAG 服务层：Corpus / Document 管理

from __future__ import annotations

from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from application.rag.dto import (
    CorpusCreateRequest,
    CorpusUpdateRequest,
    CorpusResponse,
    CorpusListResponse,
    DocumentCreateRequest,
    DocumentResponse,
    DocumentListResponse,
)
from infrastructure.repositories.rag_repository import RAGRepository


class RAGService:
    """
    业务逻辑层：
    - 做基本校验
    - 调用仓储
    - 返回 DTO 给 router / 脚本
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = RAGRepository(db)

    # ---------- Corpus ----------

    async def create_corpus(self, req: CorpusCreateRequest) -> CorpusResponse:
        orm = await self.repo.create_corpus(
            name=req.name,
            type=req.type,
            description=req.description,
            owner_id=req.owner_id,
            default_embedding_alias=req.default_embedding_alias,
            vector_store_type=req.vector_store_type,
            es_index=req.es_index,
            is_active=True,
        )
        await self.db.commit()
        return CorpusResponse.model_validate(orm)

    async def update_corpus(
        self,
        corpus_id: int,
        req: CorpusUpdateRequest,
    ) -> Optional[CorpusResponse]:
        fields: Dict[str, Any] = {}
        if req.name is not None:
            fields["name"] = req.name
        if req.type is not None:
            fields["type"] = req.type
        if req.description is not None:
            fields["description"] = req.description
        if req.is_active is not None:
            fields["is_active"] = req.is_active
        if req.default_embedding_alias is not None:
            fields["default_embedding_alias"] = req.default_embedding_alias
        if req.vector_store_type is not None:
            fields["vector_store_type"] = req.vector_store_type
        if req.es_index is not None:
            fields["es_index"] = req.es_index

        orm = await self.repo.update_corpus(corpus_id, fields)
        await self.db.commit()
        if not orm:
            return None
        return CorpusResponse.model_validate(orm)

    async def get_corpus(self, corpus_id: int) -> Optional[CorpusResponse]:
        orm = await self.repo.get_corpus(corpus_id)
        if not orm:
            return None
        return CorpusResponse.model_validate(orm)

    async def list_corpora(self) -> CorpusListResponse:
        orms = await self.repo.list_corpora()
        items = [CorpusResponse.model_validate(o) for o in orms]
        return CorpusListResponse(items=items)

    # ---------- Document ----------

    async def create_document(
        self,
        corpus_id: int,
        req: DocumentCreateRequest,
    ) -> DocumentResponse:
        # 简单校验：知识库是否存在、是否 active
        corpus = await self.repo.get_corpus(corpus_id)
        if not corpus:
            raise ValueError(f"corpus not found, id={corpus_id}")
        if not corpus.is_active:
            raise RuntimeError(f"corpus is not active, id={corpus_id}")

        orm = await self.repo.create_document(
            corpus_id=corpus_id,
            source_type=req.source_type,
            source_uri=req.source_uri,
            file_name=req.file_name,
            mime_type=req.mime_type,
            extra_meta=req.extra_meta,
        )
        await self.db.commit()
        return DocumentResponse.model_validate(orm)

    async def get_document(self, doc_id: int) -> Optional[DocumentResponse]:
        orm = await self.repo.get_document(doc_id)
        if not orm:
            return None
        return DocumentResponse.model_validate(orm)

    async def list_documents_by_corpus(
        self,
        corpus_id: int,
    ) -> DocumentListResponse:
        orms = await self.repo.list_documents_by_corpus(corpus_id)
        items = [DocumentResponse.model_validate(o) for o in orms]
        return DocumentListResponse(items=items)
