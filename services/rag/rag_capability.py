# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: RAG 能力封装（复用现有 SearchService；对外提供稳定接口，供 workflow/tool-calling 调用）

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from domains.rag_domain import SearchRequest, SearchResponse
from infrastructures.db.repository.rag_repository import RagRepository
from infrastructures.embedding.embedder_router import create_embedder
from infrastructures.index.index_router import create_es_index, create_milvus_index
from infrastructures.vlogger import vlogger
from services.rag.search_service import SearchService


_repo = RagRepository()
_search_service: Optional[SearchService] = None


def _get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService(
            repo=_repo,
            embedder=create_embedder(),
            milvus_index=create_milvus_index(),
            es_index=create_es_index(),
        )
    return _search_service


class RagCapability:
    async def search(
        self,
        db: AsyncSession,
        *,
        kb_space: str,
        query: str,
        top_k: int = 10,
        request_id: Optional[str] = None,
    ) -> SearchResponse:
        vlogger.info("rag.search space=%s top_k=%s rid=%s", kb_space, top_k, request_id or "-")
        svc = _get_search_service()
        req = SearchRequest(kb_space=str(kb_space), query=str(query), top_k=int(top_k))
        return await svc.search(db, req)
