# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Dependencies for spider(results) DB sessions (read-only).

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.spider_orm.spider_orm_base import SpiderAsyncSessionFactory


async def get_spider_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a spider(results) DB session.

    Read-only policy:
        - We never commit.
        - Always rollback at the end to ensure no accidental writes are persisted.
    """
    async with SpiderAsyncSessionFactory() as session:
        try:
            yield session
        finally:
            # even for pure reads, rollback keeps the policy explicit.
            await session.rollback()
