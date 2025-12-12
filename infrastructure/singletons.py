# -*- coding: utf-8 -*-
# @File: singletons.py
# @Author: yaccii
# @Time: 2025-12-10 22:42
# @Description:
from __future__ import annotations
from typing import Optional

from infrastructure.search.es_client import ESClient
from infrastructure.vector_store.impl_faiss import FaissVectorStore
from infrastructure.llm.llm_registry import LLMRegistry

_VEC: Optional[FaissVectorStore] = None
_ES: Optional[ESClient] = None
_LLM: Optional[LLMRegistry] = None

def get_vector_store() -> FaissVectorStore:
    global _VEC
    if _VEC is None:
        _VEC = FaissVectorStore()
    return _VEC

def get_es_client() -> ESClient:
    global _ES
    if _ES is None:
        _ES = ESClient()
    return _ES

def get_llm_registry() -> LLMRegistry:
    global _LLM
    if _LLM is None:
        _LLM = LLMRegistry()
    return _LLM
