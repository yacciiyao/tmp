# -*- coding: utf-8 -*-
# @File: infrastructure/vector_store/milvus_store.py
# @Author: yaccii
# @Description: 基于 Milvus 的向量库实现（当前为占位骨架）

from __future__ import annotations

from typing import Any, Dict, List, Optional

from infrastructure.vector_store.vector_store_base import ScoredVector, VectorStore


class MilvusVectorStore(VectorStore):
    """
    Milvus 向量库占位实现。

    说明：
    - 目前仅保留接口，实际使用时请根据具体 Milvus 部署和 SDK 完成实现；
    - 接口与 FaissVectorStore 一致，便于在 VectorStoreManager 中平滑切换。
    """

    def __init__(
        self,
        uri: str = "http://localhost:19530",
        user: Optional[str] = None,
        password: Optional[str] = None,
        db_name: str = "default",
    ) -> None:
        # 这里暂不初始化真实客户端，避免引入多余依赖
        # 后续你可以接入 pymilvus，并在此完成连接与 collection 管理。
        self._uri = uri
        self._user = user
        self._password = password
        self._db_name = db_name

        raise RuntimeError(
            "MilvusVectorStore 当前为占位实现，如需使用 Milvus，请在 "
            "`infrastructure/vector_store/milvus_store.py` 中补全逻辑。"
        )

    async def add_embeddings(
        self,
        corpus_id: int,
        doc_id: int,
        chunk_ids: List[int],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> List[int]:
        raise NotImplementedError("MilvusVectorStore.add_embeddings 未实现")

    async def search(
        self,
        corpus_id: int,
        query_embedding: List[float],
        top_k: int = 8,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ScoredVector]:
        raise NotImplementedError("MilvusVectorStore.search 未实现")
