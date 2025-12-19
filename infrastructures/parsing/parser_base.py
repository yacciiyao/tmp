# -*- coding: utf-8 -*-
# @File: parser_base.py
# @Author: yaccii
# @Time: 2025-12-15 16:48
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
