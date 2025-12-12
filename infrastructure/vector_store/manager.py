# -*- coding: utf-8 -*-
# @File: infrastructure/vector_store/manager.py
from __future__ import annotations

from typing import Dict, Optional

from infrastructure import mlogger
from infrastructure.config import settings
from .base import VectorStore
from .impl_faiss import FaissVectorStore
from .impl_milvus import MilvusVectorStore


class VectorStoreManager:
    _instances: Dict[str, VectorStore] = {}

    @classmethod
    def get_store(cls, kind: Optional[str] = None) -> VectorStore:
        k = (kind or settings.vector_store_type or "faiss").lower()
        if k in cls._instances:
            return cls._instances[k]

        if k == "faiss":
            inst: VectorStore = FaissVectorStore(use_inner_product=True)
        elif k == "milvus":
            inst = MilvusVectorStore(
                uri=getattr(settings, "milvus_uri", None),
                user=getattr(settings, "milvus_username", None),
                password=getattr(settings, "milvus_password", None),
                metric_type="IP",
                index_type="FLAT",
                index_params={},
                search_params={"nprobe": 10},
            )
        else:
            raise ValueError(f"unsupported vector_store_type: {k}")

        cls._instances[k] = inst
        mlogger.info("VectorStoreManager", "init", kind=k)
        return inst

    @classmethod
    def get_default_store(cls) -> VectorStore:
        return cls.get_store(settings.vector_store_type or "faiss")
