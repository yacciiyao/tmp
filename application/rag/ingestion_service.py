# -*- coding: utf-8 -*-
# @File: application/rag/ingestion_service.py
# @Author: yaccii
# @Description: RAG 入库服务（解析 -> 切分 -> 嵌入 -> 向量库 -> ES），向量库/存储均按配置驱动

from __future__ import annotations

import inspect
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure import mlogger
from infrastructure.db.models.rag_orm import RAGDocumentStatus
from infrastructure.llm.llm_registry import LLMRegistry
from infrastructure.rag.embeddings import EmbeddingEngine
from infrastructure.rag.loader import load_content
from infrastructure.rag.splitter import split_text
from infrastructure.repositories.rag_repository import RAGRepository
from infrastructure.search.es_client import ESClient
from infrastructure.vector_store import VectorStoreManager


class IngestionResult(BaseModel):
    doc_id: int
    status: str
    num_chunks: int = 0
    error_msg: Optional[str] = None


class IngestionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = RAGRepository(db)
        self.es = ESClient()
        self.llm = LLMRegistry()
        self.vs_manager = VectorStoreManager()

    async def ingest_document(self, doc_id: int) -> IngestionResult:
        doc = await self.repo.get_document(doc_id)
        if not doc:
            return IngestionResult(doc_id=doc_id, status="failed", error_msg="document not found")

        corpus = await self.repo.get_corpus(doc.corpus_id)
        if not corpus or not corpus.is_active:
            await self.repo.mark_document_status(doc.id, RAGDocumentStatus.FAILED, "corpus inactive")
            await self.db.commit()
            return IngestionResult(doc_id=doc_id, status="failed", error_msg="corpus inactive")

        if not corpus.default_embedding_alias:
            await self.repo.mark_document_status(doc.id, RAGDocumentStatus.FAILED, "missing default_embedding_alias")
            await self.db.commit()
            return IngestionResult(doc_id=doc_id, status="failed", error_msg="missing default_embedding_alias")

        # 标 processing
        await self.repo.mark_document_status(doc.id, RAGDocumentStatus.PROCESSING)
        await self.db.commit()

        try:
            # 1) 解析
            content = await load_content(
                source_type=doc.source_type,
                source_uri=doc.source_uri,
                mime_type=doc.mime_type,
                extra_meta=doc.extra_meta,
            )
            if not content:
                raise ValueError("empty content after load_content")

            # 2) 切分
            raw_chunks = split_text(content)
            if not raw_chunks:
                raise ValueError("no chunks after split_text")

            chunk_items: List[Dict[str, Any]] = []
            for idx, text in enumerate(raw_chunks):
                chunk_items.append(
                    {
                        "chunk_index": idx,
                        "text": text,
                        "meta": {
                            "owner_id": doc.owner_id,
                            "uploader_id": doc.uploader_id,
                            "file_name": doc.file_name,
                        },
                    }
                )
            chunk_orms = await self.repo.add_chunks(corpus.id, doc.id, chunk_items)
            await self.db.commit()

            # 3) 嵌入
            client_or_coro = self.llm.get_client(corpus.default_embedding_alias)
            embed_client = await client_or_coro if inspect.isawaitable(client_or_coro) else client_or_coro
            engine = EmbeddingEngine(embed_client)
            embeddings = await engine.embed_documents([c.text for c in chunk_orms])

            # 4) 向量库
            store = self.vs_manager.get_store(corpus.vector_store_type or "faiss")
            metadatas = [
                {"corpus_id": corpus.id, "doc_id": doc.id, "chunk_id": c.id, "owner_id": doc.owner_id}
                for c in chunk_orms
            ]
            vector_ids = await store.add_embeddings(
                corpus_id=corpus.id,
                doc_id=doc.id,
                chunk_ids=[c.id for c in chunk_orms],
                embeddings=embeddings,
                metadatas=metadatas,
            )
            await self.repo.update_chunk_vector_ids([c.id for c in chunk_orms], vector_ids)
            await self.db.commit()

            # 5) ES（失败不阻断）
            try:
                docs_for_es = [
                    {
                        "id": str(c.id),
                        "text": c.text,
                        "corpus_id": corpus.id,
                        "doc_id": doc.id,
                        "chunk_id": c.id,
                        "owner_id": doc.owner_id,
                        "file_name": doc.file_name,
                        "is_active": True,
                    }
                    for c in chunk_orms
                ]
                await self.es.index_chunks(
                    index=corpus.es_index,
                    corpus_id=corpus.id,
                    docs=docs_for_es,
                    refresh=False,
                )
            except Exception as e:
                mlogger.warning("IngestionService", "es_index_fail", doc_id=doc.id, error=str(e))

            # 6) 完成
            await self.repo.mark_document_status(doc.id, RAGDocumentStatus.READY, num_chunks=len(chunk_orms))
            await self.db.commit()
            return IngestionResult(doc_id=doc.id, status="ready", num_chunks=len(chunk_orms))

        except Exception as e:
            await self.repo.mark_document_status(doc.id, RAGDocumentStatus.FAILED, error_msg=str(e))
            await self.db.commit()
            mlogger.exception("IngestionService", "ingest_error", doc_id=doc.id, err=str(e))
            return IngestionResult(doc_id=doc.id, status="failed", error_msg=str(e))
