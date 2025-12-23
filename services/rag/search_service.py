# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: RAG 检索服务（BM25/向量/混合召回 + 结果融合）

from __future__ import annotations

from typing import Any, List, Tuple, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from domains.error_domain import AppError
from domains.rag_domain import SearchRequest, SearchResponse, SearchHit
from infrastructures.db.repository.rag_repository import RagRepository
from infrastructures.vconfig import vconfig


class SearchService:
    def __init__(self, repo: RagRepository, embedder: Any, milvus_index: Any, es_index: Any):
        self.repo = repo
        self.embedder = embedder
        self.milvus_index = milvus_index
        self.es_index = es_index

    @staticmethod
    def _backend() -> str:
        backend = (vconfig.index_backend or "").strip().lower() or "hybrid"
        if backend not in {"vector", "bm25", "hybrid"}:
            return "hybrid"
        return backend

    @staticmethod
    def _es_enabled() -> bool:
        return bool(vconfig.es_enabled)

    @staticmethod
    def _milvus_enabled() -> bool:
        return bool(vconfig.milvus_enabled)

    async def search(self, db: AsyncSession, req: SearchRequest) -> SearchResponse:
        query = (req.query or "").strip()
        if not query:
            raise AppError(code="search.empty_query", message="query is required", http_status=400)

        kb_space = (req.kb_space or "default").strip() or "default"
        top_k = int(req.top_k or 10)
        if top_k <= 0:
            raise AppError(code="search.invalid_top_k", message="top_k must be > 0", http_status=400)
        backend = self._backend()

        es_ok = self._es_enabled()
        vec_ok = self._milvus_enabled()

        if backend == "vector" and not vec_ok:
            raise AppError(code="search.vector_disabled", message="Milvus is disabled", http_status=503)
        if backend == "bm25" and not es_ok:
            raise AppError(code="search.bm25_disabled", message="Elasticsearch is disabled", http_status=503)
        if backend == "hybrid":
            if not es_ok and vec_ok:
                backend = "vector"
            elif es_ok and not vec_ok:
                backend = "bm25"
            elif not es_ok and not vec_ok:
                raise AppError(code="search.no_index", message="Both Milvus and Elasticsearch are disabled",
                               http_status=503)

        vec_pairs: List[Tuple[str, float]] = []
        es_pairs: List[Tuple[str, float]] = []

        if backend in {"vector", "hybrid"}:
            q_vec = await self.embedder.embed_query(query)
            vec_pairs = await self.milvus_index.search(kb_space=kb_space, query_vector=q_vec, top_k=top_k * 5)

        if backend in {"bm25", "hybrid"}:
            es_hits = await self.es_index.search(kb_space=kb_space, query=query, top_k=top_k * 5)
            es_pairs = [(str(h.chunk_id), float(h.score)) for h in es_hits]

        fused = self._merge(vec_pairs, es_pairs, backend)
        chunk_ids: List[str] = []
        seen_ids = set()
        for cid, _ in fused[: top_k * 5]:
            cid = str(cid)
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            chunk_ids.append(cid)

        chunks = await self.repo.get_searchable_chunks_by_ids(db, chunk_ids=chunk_ids, kb_space=kb_space)
        by_id = {str(c.chunk_id): c for c in chunks}

        hits: List[SearchHit] = []
        seen_doc: Dict[int, int] = {}

        max_per_doc = int(vconfig.search_max_per_doc)

        for cid, score in fused:
            c = by_id.get(str(cid))
            if not c:
                continue
            if seen_doc.get(c.document_id, 0) >= max_per_doc:
                continue
            seen_doc[c.document_id] = seen_doc.get(c.document_id, 0) + 1

            hits.append(
                SearchHit(
                    chunk_id=str(c.chunk_id),
                    document_id=int(c.document_id),
                    kb_space=str(c.kb_space),
                    index_version=int(c.index_version),
                    content=str(c.content),
                    meta=(dict(c.locator) if c.locator else None),
                    score=float(score),
                )
            )
            if len(hits) >= top_k:
                break

        return SearchResponse(kb_space=kb_space, query=query, top_k=top_k, backend=backend, hits=hits)

    @staticmethod
    def _merge(
            vec_pairs: List[Tuple[str, float]],
            es_pairs: List[Tuple[str, float]],
            backend: str,
    ) -> List[Tuple[str, float]]:
        # Keep behaviour stable:
        # - vector: sort by score desc, tie-break by chunk_id
        # - bm25: sort by score desc, tie-break by chunk_id
        # - hybrid: RRF fusion, then sort by fused score desc, tie-break by chunk_id
        if backend == "vector":
            pairs = [(str(cid), float(score)) for cid, score in vec_pairs]
            pairs.sort(key=lambda x: (-x[1], x[0]))
            return pairs

        if backend == "bm25":
            pairs = [(str(cid), float(score)) for cid, score in es_pairs]
            pairs.sort(key=lambda x: (-x[1], x[0]))
            return pairs

        # hybrid: Reciprocal Rank Fusion
        def rrf(r_pairs: List[Tuple[str, float]], k: int = 60) -> Dict[str, float]:
            out: Dict[str, float] = {}
            for rank, (cid, _) in enumerate(r_pairs, start=1):
                cid = str(cid)
                out[cid] = out.get(cid, 0.0) + 1.0 / (k + rank)
            return out

        a = rrf(vec_pairs)
        b = rrf(es_pairs)
        keys = set(a.keys()) | set(b.keys())
        fused = [(cid, a.get(cid, 0.0) + b.get(cid, 0.0)) for cid in keys]
        fused.sort(key=lambda x: (-x[1], x[0]))
        return fused
