# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import hashlib
from typing import List

import numpy as np


class DummyEmbedder:
    """幂等离线测试 embedding"""

    def __init__(self, dim: int = 64):
        self.dim = dim

    async def embed_query(self, text: str) -> List[float]:
        return self._hash_vector(text)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_vector(t) for t in texts]

    def _hash_vector(self, text: str) -> List[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        arr = np.frombuffer(h, dtype=np.uint8).astype(np.float32)
        if len(arr) >= self.dim:
            arr = arr[: self.dim]
        else:
            arr = np.pad(arr, (0, self.dim - len(arr)), "wrap")
        return (arr / 255.0).tolist()
