# -*- coding: utf-8 -*-
# @File: infrastructure/search/es_client.py
# @Author: yaccii
# @Description:
#   Elasticsearch 客户端封装（BM25）
#   - 支持：创建索引、批量写入、搜索、删除索引
#   - ES 关闭时自动进入 NO-OP 模式，调用安全
#   - 与 IngestionService / RAGService 的既有调用保持兼容

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch, helpers  # type: ignore

from infrastructure import mlogger
from infrastructure.config import settings


class ESClient:
    def __init__(self) -> None:
        # 是否启用
        self._active: bool = bool(getattr(settings, "es_enabled", False))
        self._client: Optional[Elasticsearch] = None

        if not self._active:
            mlogger.info("ESClient", "init:noop", msg="ES disabled; running in NO-OP mode")
            return

        if Elasticsearch is None:
            mlogger.warning("ESClient", "init:no_elastic_pkg", msg="elasticsearch package not installed; NO-OP mode")
            self._active = False
            return

        scheme = getattr(settings, "es_scheme", "http")
        host = getattr(settings, "es_host", "127.0.0.1")
        port = int(getattr(settings, "es_port", 9200))
        username = getattr(settings, "es_username", "") or None
        password = getattr(settings, "es_password", "") or None

        url = f"{scheme}://{host}:{port}"
        kwargs: Dict[str, Any] = {"hosts": [url]}
        if username and password:
            kwargs["basic_auth"] = (username, password)  # elasticsearch-py 8.x

        try:
            self._client = Elasticsearch(**kwargs)
            # 触发一次 info，验证连接
            self._client.info()
            mlogger.info("ESClient", "init:ok", url=url)
        except Exception as e:
            mlogger.warning("ESClient", "init:fail", url=url, error=str(e))
            self._client = None
            self._active = False

        self.index_prefix = (getattr(settings, "es_index_prefix", "") or "").strip()

    # -------------------- 内部：索引名与映射 --------------------

    def _full_index(self, name: str) -> str:
        if self.index_prefix:
            return f"{self.index_prefix}_{name}"
        return name

    @staticmethod
    def _mappings() -> Dict[str, Any]:
        # 简单 BM25 配置；text 字段作为全文域
        return {
            "settings": {
                "number_of_shards": int(getattr(settings, "es_number_of_shards", 1)),
                "number_of_replicas": int(getattr(settings, "es_number_of_replicas", 0)),
                "analysis": {
                    "analyzer": {
                        "default": {"type": "standard"}
                    }
                }
            },
            "mappings": {
                "dynamic": "false",
                "properties": {
                    "text": {"type": "text"},
                    "corpus_id": {"type": "long"},
                    "doc_id": {"type": "long"},
                    "chunk_id": {"type": "long"},
                    "owner_id": {"type": "long"},
                    "source_type": {"type": "keyword"},
                    "source_uri": {"type": "keyword"},
                    "file_name": {"type": "keyword"},
                    "mime_type": {"type": "keyword"},
                },
            },
        }

    # -------------------- 同步 API（供 Service 直接调用） --------------------

    def create_index_if_not_exists(self, index: str) -> None:
        """
        创建索引（若不存在）。
        """
        if not self._active or self._client is None:
            mlogger.info("ESClient", "create_index:noop", index=index)
            return

        idx = self._full_index(index)
        try:
            if not self._client.indices.exists(index=idx):  # type: ignore
                self._client.indices.create(index=idx, **self._mappings())  # type: ignore
                mlogger.info("ESClient", "create_index", index=idx)
        except Exception as e:
            mlogger.warning("ESClient", "create_index:error", index=idx, error=str(e))

    def index_documents(self, index: str, docs: List[Dict[str, Any]]) -> None:
        """
        批量写入 Chunk 文档。
        docs 需要包含：id, text, corpus_id, doc_id, chunk_id, owner_id, source_type, source_uri, file_name, mime_type
        """
        if not self._active or self._client is None or not docs:
            if not docs:
                mlogger.info("ESClient", "index_documents:skip", msg="empty docs")
            else:
                mlogger.info("ESClient", "index_documents:noop", index=index)
            return

        idx = self._full_index(index)
        actions = (
            {
                "_op_type": "index",
                "_index": idx,
                "_id": d.get("id"),
                "text": d.get("text") or "",
                "corpus_id": int(d.get("corpus_id", 0)),
                "doc_id": int(d.get("doc_id", 0)),
                "chunk_id": int(d.get("chunk_id", 0)),
                "owner_id": int(d.get("owner_id", 0)),
                "source_type": d.get("source_type") or "",
                "source_uri": d.get("source_uri") or "",
                "file_name": (d.get("file_name") or "")[:255],
                "mime_type": (d.get("mime_type") or "")[:100],
            }
            for d in docs
        )
        try:
            helpers.bulk(self._client, actions, refresh="false")  # type: ignore
            mlogger.info("ESClient", "bulk_index_ok", index=idx, count=len(docs))
        except Exception as e:
            mlogger.warning("ESClient", "bulk_index_error", index=idx, error=str(e))

    def search(
        self,
        index: str,
        query: str,
        top_k: int = 8,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        召回文本：返回统一结构：
        [{"chunk_id": int, "doc_id": int, "score": float, "text": str, ...}, ...]
        """
        if not self._active or self._client is None or not query.strip():
            return []

        idx = self._full_index(index)
        must_clause: List[Dict[str, Any]] = [
            {"multi_match": {"query": query, "fields": ["text"]}}
        ]
        filter_clause: List[Dict[str, Any]] = []
        if filters:
            for k, v in filters.items():
                filter_clause.append({"term": {k: v}})

        body = {"query": {"bool": {"must": must_clause, "filter": filter_clause}}}
        try:
            resp = self._client.search(index=idx, query=body["query"], size=top_k)  # type: ignore
        except Exception as e:
            mlogger.warning("ESClient", "search:error", index=idx, error=str(e))
            return []

        hits = resp.get("hits", {}).get("hits", [])  # type: ignore
        out: List[Dict[str, Any]] = []
        for h in hits:
            src = h.get("_source", {})  # type: ignore
            score = float(h.get("_score") or 0.0)  # type: ignore
            out.append(
                {
                    "chunk_id": int(src.get("chunk_id", 0)),
                    "doc_id": int(src.get("doc_id", 0)),
                    "score": score,
                    "text": src.get("text") or "",
                    "source_type": src.get("source_type"),
                    "source_uri": src.get("source_uri"),
                    "file_name": src.get("file_name"),
                    "mime_type": src.get("mime_type"),
                }
            )
        return out

    def delete_index(self, index: str) -> None:
        """
        删除索引（后台管理）。
        """
        if not self._active or self._client is None:
            mlogger.info("ESClient", "delete_index:noop", index=index)
            return
        idx = self._full_index(index)
        try:
            if self._client.indices.exists(index=idx):  # type: ignore
                self._client.indices.delete(index=idx, ignore_unavailable=True)  # type: ignore
                mlogger.info("ESClient", "delete_index_ok", index=idx)
        except Exception as e:
            mlogger.warning("ESClient", "delete_index_error", index=idx, error=str(e))
