# -*- coding: utf-8 -*-
# @File: __init__.py
# @Author: yaccii
# @Time: 2025-12-07 11:53
# @Description:
# -*- coding: utf-8 -*-
# @File: infrastructure/vector_store/__init__.py
# @Author: yaccii
# @Description: 向量库管理器（按类型路由到具体实现）

from __future__ import annotations

from typing import Dict, Optional

from infrastructure.vector_store.base import VectorStore


class VectorStoreManager:
    """
    向量库管理器：
    - 根据 store_type 返回对应的 VectorStore 实例；
    - 默认类型由上层注入（通常来自 settings.VECTOR_STORE_TYPE）；
    - 实例懒加载并单例缓存。
    """

    def __init__(self, default_store_type: str = "faiss") -> None:
        self._default_type = (default_store_type or "faiss").lower()
        self._stores: Dict[str, VectorStore] = {}

    def get_store(self, store_type: Optional[str] = None) -> VectorStore:
        store_type = (store_type or self._default_type).lower()

        if store_type in self._stores:
            return self._stores[store_type]

        if store_type == "faiss":
            from infrastructure.vector_store.impl_faiss import FaissVectorStore

            store: VectorStore = FaissVectorStore()
        elif store_type == "milvus":
            from infrastructure.vector_store.impl_milvus import MilvusVectorStore

            store = MilvusVectorStore()
        else:
            raise ValueError(f"Unknown vector store type: {store_type}")

        self._stores[store_type] = store
        return store
