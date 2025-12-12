# -*- coding: utf-8 -*-
# @File: infrastructure/vector_store/impl_milvus.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from infrastructure import mlogger
from .base import VectorStore

try:
    from pymilvus import (
        connections,
        FieldSchema,
        CollectionSchema,
        DataType,
        Collection,
        utility,
    )
except Exception as e:  # pragma: no cover
    raise RuntimeError("MilvusVectorStore requires 'pymilvus' to be installed") from e


class MilvusVectorStore(VectorStore):
    """
    每个 corpus 一个 collection：
      - vector_id: INT64, PK, auto_id
      - corpus_id/doc_id/chunk_id/owner_id/is_active
      - embedding: FLOAT_VECTOR[dim]
    metric: IP（入库/查询时 L2 归一化，分数越大越相似）
    """

    def __init__(
        self,
        *,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        alias: str = "default",
        metric_type: str = "IP",
        index_type: str = "FLAT",
        index_params: Optional[Dict[str, Any]] = None,
        search_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.alias = alias
        self.metric_type = metric_type.upper()
        self.index_type = index_type.upper()
        self.index_params = index_params or {}
        self.search_params = search_params or {"nprobe": 10}

        self._connect(uri=uri, user=user, password=password, alias=alias)
        self._dim_cache: Dict[str, int] = {}

    # ---------- helpers ----------

    @staticmethod
    def _collection_name(corpus_id: int) -> str:
        return f"rag_corpus_{int(corpus_id)}"

    @staticmethod
    def _to_f32_matrix(v: List[List[float]] | List[float]) -> np.ndarray:
        arr = np.array(v, dtype="float32")
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr

    @staticmethod
    def _l2_normalize(x: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(x, axis=1, keepdims=True) + 1e-12
        return x / norms

    def _connect(self, *, uri: Optional[str], user: Optional[str], password: Optional[str], alias: str) -> None:
        try:
            if alias in connections.list_connections() and connections.has_connection(alias):
                return
        except Exception:
            pass
        connections.connect(alias=alias, uri=uri or "http://127.0.0.1:19530", user=user, password=password)
        mlogger.info("MilvusVectorStore", "connected", uri=uri or "http://127.0.0.1:19530", alias=alias)

    def _get_or_create_collection(self, corpus_id: int, dim: int) -> Collection:
        name = self._collection_name(corpus_id)

        if not utility.has_collection(name, using=self.alias):
            fields = [
                FieldSchema(name="vector_id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="corpus_id", dtype=DataType.INT64),
                FieldSchema(name="doc_id", dtype=DataType.INT64),
                FieldSchema(name="chunk_id", dtype=DataType.INT64),
                FieldSchema(name="owner_id", dtype=DataType.INT64),
                FieldSchema(name="is_active", dtype=DataType.BOOL),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=int(dim)),
            ]
            schema = CollectionSchema(fields=fields, description=f"RAG corpus {corpus_id}")
            col = Collection(name=name, schema=schema, using=self.alias)
            mlogger.info("MilvusVectorStore", "create_collection", name=name, dim=dim)

            try:
                col.create_index(
                    field_name="embedding",
                    index_params={
                        "metric_type": self.metric_type,
                        "index_type": self.index_type,
                        "params": self.index_params,
                    },
                )
            except Exception as e:
                mlogger.warning("MilvusVectorStore", "create_index_fail", name=name, error=str(e))
            self._dim_cache[name] = dim
            return col

        col = Collection(name=name, using=self.alias)
        try:
            vec_field = next(f for f in col.schema.fields if f.name == "embedding")
            fd = None
            if hasattr(vec_field, "params") and isinstance(vec_field.params, dict):
                fd = vec_field.params.get("dim")
            if fd is None and hasattr(vec_field, "properties") and isinstance(vec_field.properties, dict):
                fd = vec_field.properties.get("dim")
            if fd is None:
                fd = self._dim_cache.get(name, dim)
            fd = int(fd)
            if fd != int(dim):
                raise ValueError(f"Collection dim mismatch: existed={fd}, request={dim}, corpus={corpus_id}")
            self._dim_cache[name] = fd
        except Exception:
            self._dim_cache[name] = dim
        return col

    @staticmethod
    def _expr_from_filters(filters: Optional[Dict[str, Any]]) -> Optional[str]:
        if not filters:
            return None
        parts: List[str] = []
        for k, v in filters.items():
            if isinstance(v, bool):
                parts.append(f"{k} == {str(v).lower()}")
            elif isinstance(v, (int, float)):
                parts.append(f"{k} == {v}")
            else:
                s = str(v).replace('"', '\\"')
                parts.append(f'{k} == "{s}"')
        return " and ".join(parts) if parts else None

    # ---------- API ----------

    async def add_embeddings(
        self,
        *,
        corpus_id: int,
        doc_id: int,
        chunk_ids: List[int],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> List[int]:
        if not embeddings:
            return []
        if len(chunk_ids) != len(embeddings) or len(chunk_ids) != len(metadatas):
            raise ValueError("chunk_ids / embeddings / metadatas length mismatch")

        dim = len(embeddings[0])
        col = self._get_or_create_collection(corpus_id, dim)

        X = self._to_f32_matrix(embeddings)
        if self.metric_type == "IP":
            X = self._l2_normalize(X)

        n = X.shape[0]
        corpus_ids = [int(corpus_id)] * n
        doc_ids = [int(doc_id)] * n
        owner_ids = [int(m.get("owner_id", 0)) for m in metadatas]
        is_actives = [True] * n
        chunk_ids_int = [int(x) for x in chunk_ids]
        vectors = X.tolist()

        data = [corpus_ids, doc_ids, chunk_ids_int, owner_ids, is_actives, vectors]
        mr = col.insert(data)
        vector_ids = [int(pk) for pk in mr.primary_keys]
        mlogger.info("MilvusVectorStore", "insert", corpus_id=corpus_id, rows=n)
        return vector_ids

    async def search(
        self,
        *,
        corpus_id: int,
        query_embedding: List[float],
        top_k: int = 8,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        dim = len(query_embedding)
        col = self._get_or_create_collection(corpus_id, dim)

        q = self._to_f32_matrix(query_embedding)
        if self.metric_type == "IP":
            q = self._l2_normalize(q)

        expr_parts = ["is_active == true"]
        extra = self._expr_from_filters(filters)
        if extra:
            expr_parts.append(f"({extra})")
        expr = " and ".join(expr_parts)

        try:
            col.load()
        except Exception as e:
            mlogger.warning("MilvusVectorStore", "load_warn", corpus_id=corpus_id, error=str(e))

        params = {"metric_type": self.metric_type, "params": self.search_params or {}}
        output = ["corpus_id", "doc_id", "chunk_id", "owner_id", "is_active"]

        res = col.search(
            data=q.tolist(),
            anns_field="embedding",
            param=params,
            limit=int(top_k),
            expr=expr,
            output_fields=output,
        )

        out: List[Dict[str, Any]] = []
        if not res:
            return out

        hits = res[0]
        for h in hits:
            dist = float(h.distance)
            score = dist if self.metric_type == "IP" else -dist
            eid = int(h.id)
            meta = {}
            try:
                meta = dict(h.fields)
            except Exception:
                try:
                    entity = getattr(h, "entity", None) or {}
                    meta = {
                        "corpus_id": int(entity.get("corpus_id")),
                        "doc_id": int(entity.get("doc_id")),
                        "chunk_id": int(entity.get("chunk_id")),
                        "owner_id": int(entity.get("owner_id")),
                        "is_active": bool(entity.get("is_active")),
                    }
                except Exception:
                    meta = {}
            meta["vector_id"] = eid

            out.append(
                {
                    "chunk_id": int(meta.get("chunk_id", 0)),
                    "vector_id": eid,
                    "score": score,
                    "metadata": meta,
                }
            )
        return out
