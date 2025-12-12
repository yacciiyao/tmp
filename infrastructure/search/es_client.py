from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from infrastructure import mlogger
from infrastructure.config import settings

try:
    from elasticsearch import AsyncElasticsearch  # type: ignore
except Exception:  # 没装 elasticsearch 也能跑
    AsyncElasticsearch = None


class ESClient:
    """
    可选 ES：
    - 未安装依赖 / 未配置 → 自动 no-op
    - 配置后提供：ensure_index / bulk_index_chunks / search
    """

    def __init__(self) -> None:
        self._enabled = bool(AsyncElasticsearch) and bool(getattr(settings, "es_host", None))
        self._client = None

        if not self._enabled:
            return

        host = settings.es_host
        port = settings.es_port
        scheme = getattr(settings, "es_scheme", "http") or "http"
        http_auth = None
        if getattr(settings, "es_username", None) and getattr(settings, "es_password", None):
            http_auth = (settings.es_username, settings.es_password)

        self._client = AsyncElasticsearch(
            hosts=[{"host": host, "port": port, "scheme": scheme}],
            basic_auth=http_auth,
            request_timeout=10,
        )

    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    def resolve_index(self, corpus_id: int) -> str:
        prefix = getattr(settings, "es_index_prefix", "mah_") or "mah_"
        return f"{prefix}corpus_{corpus_id}"

    async def ensure_index(self, index: str) -> None:
        if not self.enabled():
            return
        assert self._client is not None

        exists = await self._client.indices.exists(index=index)
        if exists:
            return

        mapping = {
            "mappings": {
                "properties": {
                    "corpus_id": {"type": "integer"},
                    "doc_id": {"type": "integer"},
                    "chunk_id": {"type": "integer"},
                    "text": {"type": "text"},
                    "meta": {"type": "object", "enabled": True},
                }
            }
        }
        await self._client.indices.create(index=index, **mapping)
        mlogger.info("ESClient", "index_created", index=index)

    async def bulk_index_chunks(
        self,
        index: str,
        corpus_id: int,
        items: Sequence[Dict[str, Any]],
    ) -> None:
        """
        items: [{"doc_id":..,"chunk_id":..,"text":..,"meta":{...}}, ...]
        """
        if not self.enabled():
            return
        assert self._client is not None

        await self.ensure_index(index)

        ops: List[Dict[str, Any]] = []
        for it in items:
            doc_id = int(it["doc_id"])
            chunk_id = int(it["chunk_id"])
            text = it.get("text") or ""
            meta = it.get("meta") or {}

            ops.append({"index": {"_index": index, "_id": f"{doc_id}_{chunk_id}"}})
            ops.append(
                {
                    "corpus_id": int(corpus_id),
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "text": text,
                    "meta": meta,
                }
            )

        if not ops:
            return

        resp = await self._client.bulk(operations=ops, refresh=False)
        if resp.get("errors"):
            mlogger.warning("ESClient", "bulk_index_errors", index=index)

    async def search(
        self,
        index: str,
        corpus_id: int,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        返回统一 schema：
        [{"chunk_id":..,"doc_id":..,"score":..,"metadata":{...}}, ...]
        """
        if not self.enabled():
            return []
        assert self._client is not None

        must = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["text^2"],
                    "type": "best_fields",
                    "operator": "or",
                }
            }
        ]
        flt = [{"term": {"corpus_id": int(corpus_id)}}]

        # 可扩展 filters（你后续要支持 doc_id / tag 等过滤时从这里加）
        if filters:
            for k, v in filters.items():
                flt.append({"term": {k: v}})

        body = {"query": {"bool": {"must": must, "filter": flt}}}

        resp = await self._client.search(index=index, size=int(top_k), body=body)
        hits = (resp.get("hits") or {}).get("hits") or []

        out: List[Dict[str, Any]] = []
        for h in hits:
            src = h.get("_source") or {}
            out.append(
                {
                    "chunk_id": int(src.get("chunk_id") or 0),
                    "doc_id": int(src.get("doc_id") or 0),
                    "score": float(h.get("_score") or 0.0),
                    "metadata": (src.get("meta") or {}),
                }
            )
        return out

    async def close(self) -> None:
        if self.enabled():
            assert self._client is not None
            await self._client.close()
