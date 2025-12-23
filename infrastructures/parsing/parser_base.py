# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
from abc import ABC, abstractmethod


@dataclass
class ParseError(Exception):
    message: str
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


class Parser(ABC):
    @abstractmethod
    async def parse(self, *, storage_uri: str, content_type: str) -> Dict[str, Any]:
        raise NotImplementedError

    @staticmethod
    def _to_local_path(storage_uri: str) -> str:
        if storage_uri.startswith("local:"):
            return storage_uri[len("local:"):]
        raise ParseError(f"unsupported storage_uri: {storage_uri}", retryable=False)
