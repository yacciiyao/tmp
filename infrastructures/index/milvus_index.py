# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import json
from typing import Dict, Any, List, Optional, Tuple

from pymilvus import connections, Collection, FieldSchema, DataType, CollectionSchema
from pymilvus.orm import utility

from infrastructures.vconfig import vconfig


class MilvusIndex:
    def __init__(self) -> None:
        self._connected = False

    def _ensure_connected(self) -> None:
        if self._connected or not vconfig.milvus_enabled:
            return

        connections.connect(
            alias="default",
            uri=str(vconfig.milvus_uri),
            token=(str(vconfig.milvus_token).strip() or None),
            db_name=str(vconfig.milvus_database),
            secure=bool(vconfig.milvus_secure),
        )
        self._connected = True

    @staticmethod
    def _collection_name(kb_space: str) -> str:
        prefix = vconfig.milvus_collection_prefix.strip() or "rag"
        return f"{prefix}_{kb_space}"

    def _ensure_collection(self, kb_space: str, dim: int) -> Collection:
        self._ensure_connected()
        name = self._collection_name(kb_space)

        if not utility.has_collection(name):
            fields = [
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
                FieldSchema(name="kb_space", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="document_id", dtype=DataType.INT64),
                FieldSchema(name="index_version", dtype=DataType.INT32),
                FieldSchema(name="chunk_index", dtype=DataType.INT32),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=int(dim)),
            ]
            schema = CollectionSchema(fields, description="RAG chunk vectors")
            col = Collection(name=name, schema=schema)

            raw = vconfig.milvus_index_params.strip()
            if raw:
                index_params: Dict[str, Any] = json.loads(raw)
            else:
                index_params = {
                    "index_type": str(vconfig.milvus_index_type),
                    "metric_type": str(vconfig.milvus_metric_type),
                    "params": {
                        "M": int(vconfig.milvus_hnsw_m),
                        "efConstruction": int(vconfig.milvus_hnsw_ef_construction),
                    },
                }

            col.create_index(field_name="vector", index_params=index_params)
            col.load()
            return col

        col = Collection(name=name)
        col.load()
        return col

    async def upsert(self, *, chunks: List[Dict[str, Any]], vectors: List[List[float]]) -> None:
        if not vconfig.milvus_enabled:
            return
        if len(chunks) != len(vectors):
            raise ValueError(f"chunks({len(chunks)}) != vectors({len(vectors)})")

        dim = int(vconfig.embedding_dim)
        if dim <= 0:
            raise ValueError("invalid embedding dim")

        kb_space = str(chunks[0]["kb_space"]) if chunks else "default"
        col = self._ensure_collection(kb_space=kb_space, dim=dim)

        data = [
            [str(c["chunk_id"]) for c in chunks],
            [str(c["kb_space"]) for c in chunks],
            [int(c["document_id"]) for c in chunks],
            [int(c["index_version"]) for c in chunks],
            [int(c["chunk_index"]) for c in chunks],
            vectors,
        ]
        col.upsert(data)
        col.flush()

    async def delete_by_document(
            self,
            *,
            kb_space: str,
            document_id: int,
            keep_index_version: Optional[int] = None,
    ) -> int:
        if not vconfig.milvus_enabled:
            return 0

        dim = int(vconfig.embedding_dim)
        col = self._ensure_collection(kb_space=str(kb_space), dim=dim)

        expr = f"document_id == {int(document_id)}"
        if keep_index_version is not None:
            expr = expr + f" and index_version != {int(keep_index_version)}"

        res = col.delete(expr)
        col.flush()
        return int(res.delete_count or 0)

    async def search(
            self,
            *,
            kb_space: str,
            query_vector: List[float],
            top_k: int,
            document_ids: Optional[List[int]] = None,
    ) -> List[Tuple[str, float]]:
        if not vconfig.milvus_enabled:
            return []

        dim = int(vconfig.embedding_dim)
        col = self._ensure_collection(kb_space=str(kb_space), dim=dim)

        expr = None
        if document_ids:
            ids = ",".join(str(int(x)) for x in document_ids)
            expr = f"document_id in [{ids}]"

        search_params = {
            "metric_type": str(vconfig.milvus_metric_type),
            "params": {
                "nprobe": int(vconfig.milvus_search_nprobe),
                "ef": int(vconfig.milvus_search_ef),
            },
        }

        results = col.search(
            data=[query_vector],
            anns_field="vector",
            param=search_params,
            limit=int(top_k),
            expr=expr,
            output_fields=["chunk_id"],
        )

        pairs: List[Tuple[str, float]] = []
        for hits in results:
            for h in hits:
                cid = h.entity.get("chunk_id")
                if cid is None:
                    continue
                pairs.append((str(cid), float(h.distance)))

        return pairs
