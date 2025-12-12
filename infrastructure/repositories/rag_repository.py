# -*- coding: utf-8 -*-
# @File: infrastructure/repositories/rag_repository.py
# @Description: RAG 仓储层：Corpus / Document / Chunk 的持久化操作（只做 ORM/SQL）

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure import mlogger
from infrastructure.db.models.rag_orm import (
    RAGCorpusORM,
    RAGDocumentORM,
    RAGChunkORM,
    RAGDocumentStatus,
)


class RAGRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------- Corpus -------------------------------

    async def create_corpus(
        self,
        *,
        owner_id: int,
        name: str,
        description: Optional[str] = None,
        type: str = "file",
        default_embedding_alias: Optional[str] = None,
        vector_store_type: Optional[str] = None,
        es_index: Optional[str] = None,
        is_active: bool = True,
    ) -> RAGCorpusORM:
        corpus = RAGCorpusORM(
            owner_id=owner_id,
            name=name,
            description=description,
            type=type,
            default_embedding_alias=default_embedding_alias,
            vector_store_type=vector_store_type,
            es_index=es_index,
            is_active=is_active,
        )
        self.db.add(corpus)
        await self.db.flush()
        mlogger.info("RAGRepository", "create_corpus", corpus_id=corpus.id, owner_id=owner_id, name=name)
        return corpus

    async def get_corpus(self, corpus_id: int) -> Optional[RAGCorpusORM]:
        res = await self.db.execute(
            select(RAGCorpusORM).where(RAGCorpusORM.id == corpus_id)
        )
        return res.scalar_one_or_none()

    async def list_corpora(
        self,
        *,
        owner_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> List[RAGCorpusORM]:
        conds = []
        if owner_id is not None:
            conds.append(RAGCorpusORM.owner_id == owner_id)
        if active_only:
            conds.append(RAGCorpusORM.is_active.is_(True))
        stmt = select(RAGCorpusORM).where(and_(*conds)) if conds else select(RAGCorpusORM)
        stmt = stmt.order_by(desc(RAGCorpusORM.id)).limit(limit).offset(offset)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def update_corpus(self, corpus: RAGCorpusORM, **fields: Any) -> RAGCorpusORM:
        for k, v in fields.items():
            if hasattr(corpus, k) and v is not None:
                setattr(corpus, k, v)
        await self.db.flush()
        mlogger.info("RAGRepository", "update_corpus", corpus_id=corpus.id)
        return corpus

    async def soft_delete_corpus(self, corpus: RAGCorpusORM) -> None:
        corpus.is_active = False
        await self.db.flush()
        mlogger.info("RAGRepository", "soft_delete_corpus", corpus_id=corpus.id)

    # ------------------------------- Document -------------------------------

    async def create_document(
        self,
        *,
        corpus_id: int,
        owner_id: Optional[int],
        uploader_id: Optional[int],
        source_type: str,
        source_uri: str,
        file_name: Optional[str],
        mime_type: Optional[str],
        extra_meta: Optional[Dict[str, Any]] = None,
        status: RAGDocumentStatus = RAGDocumentStatus.PENDING,
    ) -> RAGDocumentORM:
        doc = RAGDocumentORM(
            corpus_id=corpus_id,
            owner_id=owner_id,
            uploader_id=uploader_id,
            source_type=source_type,
            source_uri=source_uri,
            file_name=file_name,
            mime_type=mime_type,
            status=status,
            extra_meta_json=extra_meta or {},
            is_active=True,
        )
        self.db.add(doc)
        await self.db.flush()
        mlogger.info("RAGRepository", "create_document", doc_id=doc.id, corpus_id=corpus_id)
        return doc

    async def get_document(self, doc_id: int) -> Optional[RAGDocumentORM]:
        res = await self.db.execute(
            select(RAGDocumentORM).where(RAGDocumentORM.id == doc_id)
        )
        return res.scalar_one_or_none()

    async def list_documents(
        self,
        *,
        corpus_id: int,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True,
    ) -> List[RAGDocumentORM]:
        conds = [RAGDocumentORM.corpus_id == corpus_id]
        if active_only:
            conds.append(RAGDocumentORM.is_active.is_(True))
        stmt = select(RAGDocumentORM).where(and_(*conds)).order_by(desc(RAGDocumentORM.id)).limit(limit).offset(offset)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def soft_delete_document(self, doc: RAGDocumentORM) -> None:
        doc.is_active = False
        doc.status = RAGDocumentStatus.DELETED
        # 同时软删其 chunks
        await self.db.execute(
            update(RAGChunkORM)
            .where(RAGChunkORM.doc_id == doc.id)
            .values(is_active=False)
        )
        await self.db.flush()
        mlogger.info("RAGRepository", "soft_delete_document", doc_id=doc.id)

    async def mark_document_status(
        self,
        *,
        doc: RAGDocumentORM,
        status: RAGDocumentStatus,
        error_msg: Optional[str] = None,
        num_chunks: Optional[int] = None,
    ) -> RAGDocumentORM:
        doc.status = status
        if error_msg is not None:
            doc.error_msg = error_msg
        if num_chunks is not None:
            doc.num_chunks = int(num_chunks)
        await self.db.flush()
        mlogger.info("RAGRepository", "mark_document_status", doc_id=doc.id, status=str(status))
        return doc

    async def find_existing_documents(
        self,
        *,
        corpus_id: int,
        file_name: Optional[str] = None,
        source_uri: Optional[str] = None,
        active_only: bool = True,
    ) -> List[RAGDocumentORM]:
        conds = [RAGDocumentORM.corpus_id == corpus_id]
        subconds = []
        if file_name:
            subconds.append(RAGDocumentORM.file_name == file_name)
        if source_uri:
            subconds.append(RAGDocumentORM.source_uri == source_uri)
        if subconds:
            conds.append(and_(*subconds) if len(subconds) > 1 else subconds[0])
        if active_only:
            conds.append(RAGDocumentORM.is_active.is_(True))
        stmt = select(RAGDocumentORM).where(and_(*conds))
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def deactivate_documents(self, doc_ids: Sequence[int]) -> None:
        if not doc_ids:
            return
        await self.db.execute(
            update(RAGDocumentORM)
            .where(RAGDocumentORM.id.in_(list(doc_ids)))
            .values(is_active=False, status=RAGDocumentStatus.DELETED)
        )
        await self.db.execute(
            update(RAGChunkORM)
            .where(RAGChunkORM.doc_id.in_(list(doc_ids)))
            .values(is_active=False)
        )
        await self.db.flush()
        mlogger.info("RAGRepository", "deactivate_documents", count=len(doc_ids))

    # ------------------------------- Chunk -------------------------------

    async def bulk_create_chunks(
        self,
        *,
        corpus_id: int,
        doc_id: int,
        texts: List[str],
        metas: Optional[List[Dict[str, Any]]] = None,
    ) -> List[int]:
        if not texts:
            return []
        metas = metas or [{} for _ in texts]
        if len(metas) != len(texts):
            raise ValueError("texts/metas length mismatch")

        chunk_ids: List[int] = []
        for idx, text in enumerate(texts):
            ch = RAGChunkORM(
                corpus_id=corpus_id,
                doc_id=doc_id,
                chunk_index=idx,
                text=text,
                meta_json=metas[idx] or {},
                is_active=True,
            )
            self.db.add(ch)
            await self.db.flush()
            chunk_ids.append(ch.id)

        mlogger.info("RAGRepository", "bulk_create_chunks", doc_id=doc_id, count=len(chunk_ids))
        return chunk_ids

    async def update_chunk_vector_ids(
        self,
        *,
        doc_id: int,
        mapping: Dict[int, int],  # chunk_id -> vector_id
    ) -> None:
        if not mapping:
            return
        for chunk_id, vector_id in mapping.items():
            await self.db.execute(
                update(RAGChunkORM)
                .where(and_(RAGChunkORM.id == chunk_id, RAGChunkORM.doc_id == doc_id))
                .values(vector_id=int(vector_id))
            )
        await self.db.flush()
        mlogger.info("RAGRepository", "update_chunk_vector_ids", doc_id=doc_id, count=len(mapping))

    async def list_chunks_by_doc(self, doc_id: int, active_only: bool = True) -> List[RAGChunkORM]:
        conds = [RAGChunkORM.doc_id == doc_id]
        if active_only:
            conds.append(RAGChunkORM.is_active.is_(True))
        stmt = select(RAGChunkORM).where(and_(*conds)).order_by(RAGChunkORM.chunk_index.asc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def list_chunks_by_ids(
            self,
            chunk_ids: Sequence[int],
            active_only: bool = True,
    ) -> List[RAGChunkORM]:
        if not chunk_ids:
            return []

        stmt = select(RAGChunkORM).where(RAGChunkORM.id.in_(list(chunk_ids)))

        # 兼容字段命名差异：is_active / active / status
        if active_only:
            if hasattr(RAGChunkORM, "is_active"):
                stmt = stmt.where(RAGChunkORM.is_active == True)  # noqa: E712
            elif hasattr(RAGChunkORM, "active"):
                stmt = stmt.where(RAGChunkORM.active == True)  # noqa: E712

        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def list_documents_by_ids(
            self,
            doc_ids: Sequence[int],
    ) -> List[RAGDocumentORM]:
        if not doc_ids:
            return []
        stmt = select(RAGDocumentORM).where(RAGDocumentORM.id.in_(list(doc_ids)))
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
