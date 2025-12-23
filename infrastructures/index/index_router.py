# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import Optional

from infrastructures.index.es_index import ESIndex
from infrastructures.index.milvus_index import MilvusIndex

_es_singleton: Optional[ESIndex] = None
_milvus_singleton: Optional[MilvusIndex] = None


def create_es_index() -> ESIndex:
    global _es_singleton
    if _es_singleton is None:
        _es_singleton = ESIndex()
    return _es_singleton


def create_milvus_index() -> MilvusIndex:
    global _milvus_singleton
    if _milvus_singleton is None:
        _milvus_singleton = MilvusIndex()
    return _milvus_singleton
