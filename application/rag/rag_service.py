# -*- coding: utf-8 -*-
# @File: application/rag/rag_service.py
# @Description: RAG 主服务（后台 CRUD + 上传入库 + 检索查询）
from __future__ import annotations

import inspect
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from application.rag.dto import (
    CorpusCreateRequest,
    CorpusListResponse,
    CorpusResponse,
    CorpusUpdateRequest,
    DocumentCreateRequest,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
    RAGChunkHit,
    RAGQueryRequest,
    RAGQueryResponse,
)
from application.rag.fusion.rrf import RRFFusionStrategy
from application.rag.retrieval.normalizers import normalize_dense_hits, normalize_sparse_hits
from domain.rag_retrieval import FusedHit
from infrastructure import mlogger
from infrastructure.config import settings
from infrastructure.db.models.rag_orm import (
    RAGCorpusORM,
    RAGDocumentORM,
    RAGDocumentStatus,
    RAGChunkORM,
)
from infrastructure.repositories.rag_repository import RAGRepository
from infrastructure.storage.file_storage import save_upload_file
from application.rag.ingestion_service import IngestionService
from infrastructure.rag.embeddings import EmbeddingEngine
from infrastructure.llm.llm_registry import LLMRegistry
from infrastructure.vector_store.manager import VectorStoreManager
from infrastructure.search.es_client import ESClient
from infrastructure.storage.path_utils import build_file_url


class RAGService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = RAGRepository(db)
        self.es = ESClient()

    # ---------------------------------------------------------------------
    # Corpus
    # ---------------------------------------------------------------------

    async def create_corpus(self, req: CorpusCreateRequest, *, owner_id: int) -> CorpusResponse:
        corpus = await self.repo.create_corpus(
            owner_id=owner_id,
            name=req.name,
            description=req.description,
            type="file",
            default_embedding_alias=req.default_embedding_alias,
            vector_store_type=req.vector_store_type or getattr(settings, "vector_store_type", "faiss"),
            es_index=req.es_index or None,
            is_active=True,
        )
        await self.db.commit()
        return CorpusResponse.model_validate(corpus)

    async def get_corpus(self, corpus_id: int) -> CorpusResponse:
        corpus = await self.repo.get_corpus(corpus_id)
        if not corpus:
            raise ValueError(f"corpus not found: {corpus_id}")
        return CorpusResponse.model_validate(corpus)

    async def list_corpora(
        self,
        *,
        owner_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> CorpusListResponse:
        items = await self.repo.list_corpora(
            owner_id=owner_id,
            limit=limit,
            offset=offset,
            active_only=active_only,
        )
        return CorpusListResponse(items=[CorpusResponse.model_validate(c) for c in items])

    async def update_corpus(self, corpus_id: int, req: CorpusUpdateRequest) -> CorpusResponse:
        corpus = await self.repo.get_corpus(corpus_id)
        if not corpus:
            raise ValueError(f"corpus not found: {corpus_id}")

        corpus = await self.repo.update_corpus(
            corpus,
            name=req.name,
            description=req.description,
            default_embedding_alias=req.default_embedding_alias,
            vector_store_type=req.vector_store_type,
            es_index=req.es_index,
            is_active=req.is_active,
        )
        await self.db.commit()
        return CorpusResponse.model_validate(corpus)

    async def delete_corpus(self, corpus_id: int) -> Dict[str, Any]:
        corpus = await self.repo.get_corpus(corpus_id)
        if not corpus:
            raise ValueError(f"corpus not found: {corpus_id}")
        await self.repo.soft_delete_corpus(corpus)
        await self.db.commit()
        return {"id": corpus_id, "deleted": True}

    # ---------------------------------------------------------------------
    # Document
    # ---------------------------------------------------------------------

    async def create_document(
        self,
        *,
        corpus_id: int,
        req: DocumentCreateRequest,
        uploader_id: Optional[int] = None,
    ) -> DocumentResponse:
        corpus = await self.repo.get_corpus(corpus_id)
        if not corpus:
            raise ValueError(f"corpus not found: {corpus_id}")

        # 去重：相同 (corpus, file_name) 或 (corpus, source_uri) 的旧版本全部软删
        existing = await self.repo.find_existing_documents(
            corpus_id=corpus_id,
            file_name=req.file_name,
            source_uri=req.source_uri,
            active_only=True,
        )
        if existing:
            await self.repo.deactivate_documents([d.id for d in existing])

        doc = await self.repo.create_document(
            corpus_id=corpus_id,
            owner_id=(req.owner_id if req.owner_id is not None else corpus.owner_id),
            uploader_id=uploader_id,
            source_type=req.source_type,
            source_uri=req.source_uri,
            file_name=req.file_name,
            mime_type=req.mime_type,
            extra_meta=req.extra_meta or {},
            status=RAGDocumentStatus.PENDING,
        )
        await self.db.commit()
        return DocumentResponse.model_validate(doc)

    async def get_document(self, doc_id: int) -> DocumentResponse:
        doc = await self.repo.get_document(doc_id)
        if not doc:
            raise ValueError(f"document not found: {doc_id}")
        return DocumentResponse.model_validate(doc)

    async def list_documents(self, *, corpus_id: int, limit: int = 100, offset: int = 0) -> DocumentListResponse:
        items = await self.repo.list_documents(corpus_id=corpus_id, limit=limit, offset=offset, active_only=True)
        return DocumentListResponse(items=[DocumentResponse.model_validate(d) for d in items])

    async def delete_document(self, doc_id: int) -> Dict[str, Any]:
        doc = await self.repo.get_document(doc_id)
        if not doc:
            raise ValueError(f"document not found: {doc_id}")
        await self.repo.soft_delete_document(doc)
        await self.db.commit()
        return {"id": doc_id, "deleted": True}

    async def upload_and_ingest_document(
        self,
        *,
        corpus_id: int,
        uploader_id: int,
        upload: UploadFile,
    ) -> DocumentUploadResponse:
        """
        一步式：上传文件 -> 创建文档 -> 触发入库
        """
        rel_path, url = await save_upload_file(uploader_id, upload)
        doc = await self.create_document(
            corpus_id=corpus_id,
            req=DocumentCreateRequest(
                source_type="file",
                source_uri=rel_path,
                file_name=upload.filename,
                mime_type=upload.content_type or "application/octet-stream",
                extra_meta=None,
                owner_id=uploader_id,  # 记录归属
            ),
            uploader_id=uploader_id,
        )
        # 入库
        ing = IngestionService(self.db)
        await ing.ingest_document(doc.id)

        # 重新读取以呈现最新状态
        doc2 = await self.repo.get_document(doc.id)
        assert doc2 is not None
        await self.db.commit()
        return DocumentUploadResponse(document=DocumentResponse.model_validate(doc2), rel_path=rel_path, file_url=url)

    # ---------------------------------------------------------------------
    # Query（整合：向量 + BM25 + RRF 融合）
    # ---------------------------------------------------------------------



    async def query(self, req: RAGQueryRequest) -> RAGQueryResponse:
        async def _maybe_await(x):
            return await x if inspect.isawaitable(x) else x

        corpus = await self.repo.get_corpus(req.corpus_id)
        if not corpus or not corpus.is_active:
            raise ValueError(f"corpus not found or inactive: {req.corpus_id}")

        # -------------------------
        # 1) Dense retrieval
        # -------------------------
        dense_hits = []
        if req.use_vector:
            embed_alias = (
                corpus.default_embedding_alias
                or getattr(settings, "embedding_llm_alias", None)
                or getattr(settings, "default_llm_alias", None)
            )
            try:
                llm_registry = LLMRegistry()
                if embed_alias:
                    embed_client = await _maybe_await(llm_registry.get_client(embed_alias))
                else:
                    embed_client = await _maybe_await(llm_registry.get_default_embedding_client())

                engine = EmbeddingEngine(embed_client)
                q_emb = await engine.embed_query(req.query)

                vs_kind = (corpus.vector_store_type or getattr(settings, "vector_store_type", "faiss")).lower()
                vector_store = VectorStoreManager.get_store(vs_kind)

                dense_raw = await _maybe_await(
                    vector_store.search(
                        corpus_id=req.corpus_id,
                        query_embedding=q_emb,
                        top_k=req.top_k,
                        filters=None,
                    )
                )
                dense_hits = normalize_dense_hits(dense_raw or [])
            except Exception as e:
                mlogger.warning("RAGService", "query:dense_error", corpus_id=req.corpus_id, error=str(e))
                dense_hits = []

        # -------------------------
        # 2) Sparse retrieval (ES BM25)
        # -------------------------
        sparse_hits = []
        if req.use_bm25:
            try:
                index_name = getattr(corpus, "es_index", None) or self.es.resolve_index(req.corpus_id)
                sparse_raw = await _maybe_await(
                    self.es.search(
                        index=index_name,
                        corpus_id=req.corpus_id,
                        query=req.query,
                        top_k=req.top_k,
                        filters=None,
                    )
                )
                sparse_hits = normalize_sparse_hits(sparse_raw or [])
            except Exception as e:
                mlogger.warning("RAGService", "query:es_error", corpus_id=req.corpus_id, error=str(e))
                sparse_hits = []

        # -------------------------
        # 3) Fuse
        # -------------------------
        fusion = RRFFusionStrategy(k=60.0)
        fused: List[FusedHit] = fusion.fuse(dense=dense_hits, sparse=sparse_hits, top_k=req.top_k)

        ranked_chunk_ids = [h.chunk_id for h in fused if h.chunk_id > 0]

        # -------------------------
        # 4) Batch fetch chunks + docs
        # -------------------------
        chunks = []
        if hasattr(self.repo, "list_chunks_by_ids"):
            chunks = await self.repo.list_chunks_by_ids(ranked_chunk_ids, active_only=True)
        else:
            # 兜底：逐个取（性能差但可用）
            chunks = []
            for cid in ranked_chunk_ids:
                if hasattr(self.repo, "get_chunk"):
                    c = await self.repo.get_chunk(cid)
                    if c:
                        chunks.append(c)

        chunk_by_id = {int(c.id): c for c in chunks}

        doc_ids = sorted({int(getattr(c, "doc_id", 0)) for c in chunks if int(getattr(c, "doc_id", 0)) > 0})
        docs = []
        if hasattr(self.repo, "list_documents_by_ids"):
            docs = await self.repo.list_documents_by_ids(doc_ids)
        else:
            docs = []
            for did in doc_ids:
                d = await self.repo.get_document(did)
                if d:
                    docs.append(d)

        doc_by_id = {int(d.id): d for d in docs}

        # -------------------------
        # 5) Build response hits (保序：按 fused 的顺序)
        # -------------------------
        final_hits: List[RAGChunkHit] = []
        for fh in fused:
            ch = chunk_by_id.get(int(fh.chunk_id))
            doc_id = int(getattr(ch, "doc_id", fh.doc_id)) if ch else int(fh.doc_id)
            doc_obj = doc_by_id.get(doc_id)

            source_type = getattr(doc_obj, "source_type", None) if doc_obj else None
            source_uri = getattr(doc_obj, "source_uri", None) if doc_obj else None

            source_url = None
            if source_type == "file" and source_uri:
                source_url = build_file_url(str(source_uri))
            elif source_type == "url" and source_uri:
                source_url = str(source_uri)

            final_hits.append(
                RAGChunkHit(
                    chunk_id=int(fh.chunk_id),
                    doc_id=doc_id,
                    corpus_id=req.corpus_id,
                    score=float(fh.score),
                    text=(getattr(ch, "text", "") if ch else ""),
                    source=fh.source_label,
                    source_type=source_type,
                    source_uri=source_uri,
                    source_url=source_url,
                    meta=(getattr(ch, "meta", None) if ch else (fh.metadata or {})),
                )
            )

        context = "\n\n".join([h.text for h in final_hits if h.text])

        return RAGQueryResponse(
            query=req.query,
            corpus_ids=[req.corpus_id],
            hits=final_hits,
            context_text=context,
        )