# -*- coding: utf-8 -*-
# @File: base.py
# @Author: yaccii
# @Time: 2025-12-12 17:26
# @Description:
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from domain.rag_retrieval import FusedHit, RetrieverHit


class FusionStrategy(ABC):
    @abstractmethod
    def fuse(
        self,
        dense: List[RetrieverHit],
        sparse: List[RetrieverHit],
        top_k: int,
    ) -> List[FusedHit]:
        raise NotImplementedError
