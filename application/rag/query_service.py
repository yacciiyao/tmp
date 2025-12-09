# -*- coding: utf-8 -*-
# @File: application/rag/query_service.py
# @Author: yaccii
# @Description: RAG 检索服务（Query Side）

from __future__ import annotations

import inspect
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.rag.dto import RAGQueryRequest, RAGQueryResponse, RAGChunkHit
from infrastructure import mlogger
from infrastructure.db.models import rag_orm as rag_models
from infrastructure.llm.llm_registry import LLMRegistry
from infrastructure.rag.embeddings import EmbeddingEngine
from infrastructure.search.es_client import ESClient
from infrastructure.vector_store import VectorStoreManager


class RAGQueryService:
    """
    RAG 查询侧服务：
    - 负责“query -> 向量检索 / BM25 -> 聚合 hits -> 构造上下文”
    - 不直接调用 LLM，给 ChatService / Agent 用
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.vector_store_manager = VectorStoreManager()
        self.es_client = ESClient()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def query(self, req: RAGQueryRequest) -> RAGQueryResponse:
        """
        RAG 检索主流程：
        1. 取 Corpus & 校验
        2. 向量检索（可选）
        3. BM25 检索（可选）
        4. 融合打分
        5. 查回 chunk + document 信息
        6. 组装 RAGQueryResponse
        """
        corpus = await self._get_corpus(req.corpus_id)
        if not corpus.is_active:
            raise RuntimeError(f"corpus is not active, id={corpus.id}")

        mlogger.info(
            "RAGQuery",
            "query:start",
            corpus_id=corpus.id,
            query=req.query,
            top_k=req.top_k,
            use_vector=req.use_vector,
            use_bm25=req.use_bm25,
        )

        # ---------------- Vector Search ----------------
        vector_results: List[Any] = []
        if req.use_vector and corpus.default_embedding_alias:
            try:
                q_embedding = await self._get_query_embedding(
                    alias=corpus.default_embedding_alias,
                    text=req.query,
                )
                store = self.vector_store_manager.get_store(
                    corpus.vector_store_type or "faiss"
                )
                vector_results = await store.search(
                    corpus_id=corpus.id,
                    query_embedding=q_embedding,  # 关键：这里统一用 query_embedding
                    top_k=req.top_k,
                    filters=None,
                )
            except Exception as e:
                # 向量检索失败视为降级：写日志，不中断整个 RAG
                mlogger.warning(
                    "RAGQuery",
                    "vector_search",
                    msg=f"vector search error: {e!r}",
                    corpus_id=corpus.id,
                )
                vector_results = []

        # ---------------- BM25 (ES) Search ----------------
        bm25_results: List[Any] = []
        if req.use_bm25:
            try:
                bm25_results = await self.es_client.search(
                    index=corpus.es_index,
                    corpus_id=corpus.id,
                    query=req.query,
                    top_k=req.top_k,
                    filters=None,
                )
            except Exception as e:
                # 目前 ESClient 默认是 no-op，这里只是防备未来开启 ES 之后的异常
                mlogger.warning(
                    "RAGQuery",
                    "bm25_search",
                    msg=f"bm25 search error: {e!r}",
                    corpus_id=corpus.id,
                )
                bm25_results = []

        # ---------------- Merge Results ----------------
        scored_chunks: Dict[int, float] = {}
        self._accumulate_results(scored_chunks, vector_results)
        self._accumulate_results(scored_chunks, bm25_results)

        if not scored_chunks:
            # 所有通路都返回空，直接给空结果
            return RAGQueryResponse(
                corpus_id=corpus.id,
                query=req.query,
                hits=[],
                context="",
            )

        # 按 score 排序，截断 top_k
        sorted_items: List[Tuple[int, float]] = sorted(
            scored_chunks.items(), key=lambda kv: kv[1], reverse=True
        )
        top_items = sorted_items[: req.top_k]
        top_chunk_ids = [cid for cid, _ in top_items]

        # ---------------- Load Chunk + Document ----------------
        chunk_doc_map = await self._load_chunks_and_docs(top_chunk_ids)

        hits: List[RAGChunkHit] = []
        context_parts: List[str] = []

        for chunk_id, score in top_items:
            pair = chunk_doc_map.get(chunk_id)
            if not pair:
                continue
            chunk, doc = pair
            text = chunk.text or ""
            meta = chunk.meta or {}

            hits.append(
                RAGChunkHit(
                    chunk_id=chunk.id,
                    doc_id=chunk.doc_id,
                    corpus_id=chunk.corpus_id,
                    score=score,
                    source_type=doc.source_type,
                    source_uri=doc.source_uri,
                    text=text,
                    meta=meta,
                )
            )
            context_parts.append(text)

        context = "\n\n".join(context_parts)

        mlogger.info(
            "RAGQuery",
            "query:done",
            corpus_id=corpus.id,
            query=req.query,
            top_k=req.top_k,
            hit_count=len(hits),
        )

        return RAGQueryResponse(
            corpus_id=corpus.id,
            query=req.query,
            hits=hits,
            context=context,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_corpus(self, corpus_id: int) -> rag_models.RAGCorpusORM:
        stmt = select(rag_models.RAGCorpusORM).where(
            rag_models.RAGCorpusORM.id == corpus_id
        )
        res = await self.db.execute(stmt)
        corpus = res.scalar_one_or_none()
        if corpus is None:
            raise ValueError(f"corpus not found, id={corpus_id}")
        return corpus

    async def _get_query_embedding(self, alias: str, text: str) -> List[float]:
        """
        复用 EmbeddingEngine，对 query 生成单个向量。
        """
        llm_registry = LLMRegistry()
        client_or_coro = llm_registry.get_client(alias)

        if inspect.isawaitable(client_or_coro):
            embed_client = await client_or_coro
        else:
            embed_client = client_or_coro

        if embed_client is None:
            raise RuntimeError(f"unable to get embedding client for alias={alias}")

        engine = EmbeddingEngine(embed_client)
        vecs = await engine.embed_documents([text])
        if not vecs:
            raise RuntimeError("embed_documents returned empty list for query")
        return vecs[0]

    async def _load_chunks_and_docs(
        self, chunk_ids: List[int]
    ) -> Dict[int, Tuple[rag_models.RAGChunkORM, rag_models.RAGDocumentORM]]:
        """
        一次性从 DB 拉回 topK chunk 及其所属 document。
        """
        if not chunk_ids:
            return {}

        stmt = (
            select(rag_models.RAGChunkORM, rag_models.RAGDocumentORM)
            .join(
                rag_models.RAGDocumentORM,
                rag_models.RAGChunkORM.doc_id == rag_models.RAGDocumentORM.id,
            )
            .where(rag_models.RAGChunkORM.id.in_(chunk_ids))
        )

        res = await self.db.execute(stmt)
        rows = res.all()

        mapping: Dict[int, Tuple[rag_models.RAGChunkORM, rag_models.RAGDocumentORM]] = {}
        for chunk, doc in rows:
            mapping[chunk.id] = (chunk, doc)
        return mapping

    # ---------------- Merge helpers ----------------

    @staticmethod
    def _extract_chunk_id_score(obj: Any) -> Optional[Tuple[int, float]]:
        """
        尽量兼容不同 VectorStore / ES 返回格式：
        - dict: {"chunk_id": xxx, "score": xxx} 或 {"id": xxx, "score": xxx}
        - tuple/list: (chunk_id, score)
        - 对象: .chunk_id / .id + .score/.distance/.similarity
        """
        cid: Optional[int]
        score_val: Any

        if isinstance(obj, dict):
            cid = obj.get("chunk_id") or obj.get("id")
            score_val = obj.get("score") or obj.get("distance") or obj.get(
                "similarity"
            )
        elif isinstance(obj, (list, tuple)) and len(obj) >= 2:
            cid = obj[0]
            score_val = obj[1]
        else:
            cid = getattr(obj, "chunk_id", None) or getattr(obj, "id", None)
            score_val = (
                getattr(obj, "score", None)
                or getattr(obj, "distance", None)
                or getattr(obj, "similarity", None)
            )

        if cid is None:
            return None

        try:
            score_float = float(score_val) if score_val is not None else 0.0
        except (TypeError, ValueError):
            score_float = 0.0

        return int(cid), score_float

    def _accumulate_results(
        self,
        scored_chunks: Dict[int, float],
        results: List[Any],
    ) -> None:
        """
        将向量检索 / BM25 的结果合并到一个 chunk_id -> score 字典里。
        这里采用简单的“score 累加”，后续可以替换为 RRF 等更高级融合。
        """
        for obj in results or []:
            extracted = self._extract_chunk_id_score(obj)
            if not extracted:
                continue

            cid, score = extracted
            prev = scored_chunks.get(cid, 0.0)
            scored_chunks[cid] = prev + score
