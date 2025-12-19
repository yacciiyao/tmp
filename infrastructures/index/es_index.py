# -*- coding: utf-8 -*-
# @File: es_index.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from infrastructures.vconfig import config



def _compat_headers() -> Dict[str, str]:
    """Force REST API compatibility with Elasticsearch 8.x server.

    This project may run with a newer python client (e.g. 9.x) against an ES 8.x cluster.
    ES 8 rejects 'compatible-with=9', so we pin the compatibility header to 8.
    """
    return {
        "Accept": "application/vnd.elasticsearch+json; compatible-with=8",
        "Content-Type": "application/vnd.elasticsearch+json; compatible-with=8",
    }


@dataclass
class ESSearchHit:
    chunk_id: str
    document_id: int
    chunk_index: int
    score: float
    content: str
    meta: Dict[str, Any]


class ESIndex:
    """
    Elasticsearch indexer/searcher for chunks.
    """

    def __init__(self) -> None:
        if not config.es_enabled:
            self._enabled = False
        else:
            self._enabled = True

        self._client: Optional[AsyncElasticsearch] = None

    def _require_enabled(self) -> None:
        if not self._enabled:
            raise RuntimeError("Elasticsearch is disabled (ES_ENABLED=false)")

    def _index_name(self, kb_space: str) -> str:
        prefix = config.es_index_prefix
        kb_space = (kb_space or "default").strip() or "default"
        return f"{prefix}{kb_space}"

    def _get_client(self) -> AsyncElasticsearch:
        self._require_enabled()
        if self._client is None:
            es_url = str(config.es_url or "").strip()
            if not es_url:
                raise RuntimeError("ES_URL is required when ES_ENABLED=true")

            # 认证：优先 basic_auth，其次 api_key（如果你要启用）
            username = str(config.es_username or "")
            password = str(config.es_password or "")
            api_key = str(config.es_api_key or "")

            kwargs: Dict[str, Any] = {
                "hosts": [es_url],
                "request_timeout": float(config.es_timeout_seconds),
                "headers": _compat_headers(),
            }

            # python client 8.x：basic_auth / api_key
            if username or password:
                kwargs["basic_auth"] = (username, password)
            elif api_key:
                kwargs["api_key"] = api_key

            # 不传 aiohttp_client_kwargs（你环境不支持这个参数）
            self._client = AsyncElasticsearch(**kwargs)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def ensure_index(self, kb_space: str) -> None:
        """
        确保 index 存在。mapping 只覆盖本项目必须字段。
        """
        client = self._get_client()
        index = self._index_name(kb_space)

        exists = await client.indices.exists(index=index)
        if bool(exists):
            return

        mappings = {
            "properties": {
                "chunk_id": {"type": "keyword"},
                "kb_space": {"type": "keyword"},
                "document_id": {"type": "long"},
                "index_version": {"type": "integer"},
                "chunk_index": {"type": "integer"},
                "content": {"type": "text"},
                "meta": {"type": "object", "enabled": True},
            }
        }

        settings = {
            "number_of_shards": int(config.es_number_of_shards),
            "number_of_replicas": int(config.es_number_of_replicas),
        }

        await client.indices.create(index=index, mappings=mappings, settings=settings)

    async def upsert(self, chunks: Sequence[Dict[str, Any]]) -> int:
        """
        批量写入/更新 chunks 到 ES。
        chunks 的 dict 必须包含：
        - chunk_id, kb_space, document_id, index_version, chunk_index, content
        meta 可选
        """
        client = self._get_client()
        if not chunks:
            return 0

        kb_space = str(chunks[0].get("kb_space") or "default")
        await self.ensure_index(kb_space)
        index = self._index_name(kb_space)

        actions = []
        for c in chunks:
            chunk_id = str(c["chunk_id"])
            actions.append(
                {
                    "_op_type": "index",
                    "_index": index,
                    "_id": chunk_id,
                    "_source": {
                        "chunk_id": chunk_id,
                        "kb_space": str(c.get("kb_space") or "default"),
                        "document_id": int(c.get("document_id") or 0),
                        "index_version": int(c.get("index_version") or 0),
                        "chunk_index": int(c.get("chunk_index") or 0),
                        "content": str(c.get("content") or ""),
                        "meta": dict(c.get("meta") or {}),
                    },
                }
            )

        success, _ = await async_bulk(client, actions, refresh=False)
        return int(success)

    async def delete_by_document(self, kb_space: str, document_id: int, keep_index_version: int) -> int:
        """
        删除某 document 的旧版本（保留 keep_index_version）。
        """
        client = self._get_client()
        await self.ensure_index(kb_space)
        index = self._index_name(kb_space)

        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"kb_space": kb_space}},
                        {"term": {"document_id": int(document_id)}},
                    ],
                    "must_not": [{"term": {"index_version": int(keep_index_version)}}],
                }
            }
        }

        resp = await client.delete_by_query(index=index, body=query, refresh=False, conflicts="proceed")
        return int(resp.get("deleted") or 0)

    async def search(
        self,
        kb_space: str,
        query: str,
        *,
        top_k: int = 10,
        document_ids: Optional[Sequence[int]] = None,
    ) -> List[ESSearchHit]:
        """
        基于 content 字段做全文检索（BM25）。
        """
        client = self._get_client()
        await self.ensure_index(kb_space)
        index = self._index_name(kb_space)

        must: List[Dict[str, Any]] = [{"match": {"content": {"query": query}}}]
        filt: List[Dict[str, Any]] = [{"term": {"kb_space": kb_space}}]

        if document_ids:
            filt.append({"terms": {"document_id": [int(x) for x in document_ids]}})

        body = {
            "size": int(top_k),
            "query": {"bool": {"must": must, "filter": filt}},
        }

        resp = await client.search(index=index, body=body)
        hits = resp.get("hits", {}).get("hits", []) or []

        out: List[ESSearchHit] = []
        for h in hits:
            src = h.get("_source") or {}
            out.append(
                ESSearchHit(
                    chunk_id=str(src.get("chunk_id") or h.get("_id") or ""),
                    document_id=int(src.get("document_id") or 0),
                    chunk_index=int(src.get("chunk_index") or 0),
                    score=float(h.get("_score") or 0.0),
                    content=str(src.get("content") or ""),
                    meta=dict(src.get("meta") or {}),
                )
            )
        return out
