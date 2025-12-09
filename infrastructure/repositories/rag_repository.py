# -*- coding: utf-8 -*-
# @File: infrastructure/repositories/rag_repository.py
# @Author: yaccii
# @Description: RAG 相关仓储：Corpus / Document / Chunk

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models.rag_orm import (
    RAGCorpusORM,
    RAGDocumentORM,
    RAGChunkORM,
)


class RAGRepository:
    """
    只负责 DB 读写，不做业务逻辑。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---------------- Corpus ----------------

    async def get_corpus(self, corpus_id: int) -> Optional[RAGCorpusORM]:
        return await self.db.get(RAGCorpusORM, corpus_id)

    async def list_corpora(self) -> List[RAGCorpusORM]:
        stmt = select(RAGCorpusORM).order_by(RAGCorpusORM.id.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_corpus(
        self,
        *,
        name: str,
        type: str,
        description: Optional[str],
        owner_id: int,
        default_embedding_alias: Optional[str],
        vector_store_type: Optional[str],
        es_index: Optional[str],
        is_active: bool = True,
    ) -> RAGCorpusORM:
        orm = RAGCorpusORM(
            name=name,
            type=type,
            description=description,
            owner_id=owner_id,
            default_embedding_alias=default_embedding_alias,
            vector_store_type=vector_store_type,
            es_index=es_index,
            is_active=is_active,
        )
        self.db.add(orm)
        await self.db.flush()
        await self.db.refresh(orm)
        return orm

    async def update_corpus(
        self,
        corpus_id: int,
        fields: Dict[str, Any],
    ) -> Optional[RAGCorpusORM]:
        if not fields:
            return await self.get_corpus(corpus_id)

        stmt = (
            update(RAGCorpusORM)
            .where(RAGCorpusORM.id == corpus_id)
            .values(**fields)
        )
        await self.db.execute(stmt)
        await self.db.flush()
        return await self.get_corpus(corpus_id)

    # ---------------- Document ----------------

    async def get_document(self, doc_id: int) -> Optional[RAGDocumentORM]:
        return await self.db.get(RAGDocumentORM, doc_id)

    async def list_documents_by_corpus(
        self,
        corpus_id: int,
    ) -> List[RAGDocumentORM]:
        stmt = (
            select(RAGDocumentORM)
            .where(RAGDocumentORM.corpus_id == corpus_id)
            .order_by(RAGDocumentORM.id.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_document(
        self,
        *,
        corpus_id: int,
        source_type: str,
        source_uri: str,
        file_name: Optional[str],
        mime_type: Optional[str],
        extra_meta: Optional[Dict[str, Any]],
    ) -> RAGDocumentORM:
        """
        注意：这里用 extra_meta（JSON 字段），不再有 extra_meta_json。
        """
        orm = RAGDocumentORM(
            corpus_id=corpus_id,
            source_type=source_type,
            source_uri=source_uri,
            file_name=file_name,
            mime_type=mime_type,
            status="pending",
            error_msg=None,
            num_chunks=None,
            extra_meta=extra_meta,
        )
        self.db.add(orm)
        await self.db.flush()
        await self.db.refresh(orm)
        return orm

    async def update_document_status(
        self,
        *,
        doc_id: int,
        status: str,
        error_msg: Optional[str],
        num_chunks: Optional[int],
    ) -> None:
        values: Dict[str, Any] = {
            "status": status,
            "error_msg": error_msg,
        }
        if num_chunks is not None:
            values["num_chunks"] = num_chunks

        stmt = (
            update(RAGDocumentORM)
            .where(RAGDocumentORM.id == doc_id)
            .values(**values)
        )
        await self.db.execute(stmt)
        await self.db.flush()

    # ---------------- Chunk（目前只在 Ingestion 用） ----------------

    async def get_chunks_by_doc(self, doc_id: int) -> List[RAGChunkORM]:
        stmt = (
            select(RAGChunkORM)
            .where(RAGChunkORM.doc_id == doc_id)
            .order_by(RAGChunkORM.chunk_index.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
