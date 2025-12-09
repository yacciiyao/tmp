# -*- coding: utf-8 -*-
# @File: pagination.py
# @Author: yaccii
# @Description:
from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @field_validator("page")
    @classmethod
    def _normalize_page(cls, v: int) -> int:
        return max(1, v)

    @field_validator("page_size")
    @classmethod
    def _normalize_page_size(cls, v: int) -> int:
        return max(1, min(200, v))


class PageResult(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    next_page: Optional[int] = None

    @classmethod
    def from_items(
        cls,
        items: List[T],
        total: int,
        page_params: PageParams,
    ) -> "PageResult[T]":
        if page_params.offset + len(items) < total:
            next_page = page_params.page + 1
        else:
            next_page = None

        return cls(
            items=items,
            total=total,
            page=page_params.page,
            page_size=page_params.page_size,
            next_page=next_page,
        )
