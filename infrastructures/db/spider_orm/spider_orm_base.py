# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Spider(results) DB ORM base (read-only). No migrations/DDL.

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from infrastructures.vconfig import vconfig


class SpiderBase(DeclarativeBase):
    """Declarative base for spider(results) DB."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_spider_engine() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create async engine/sessionmaker for SPIDER_DB_URL lazily.

    Notes:
        - This project must treat spider DB as read-only.
        - Do NOT call metadata.create_all for SpiderBase.
    """

    global _engine, _session_factory
    if _engine is not None and _session_factory is not None:
        return _engine, _session_factory

    _engine = create_async_engine(
        str(vconfig.spider_db_url),
        echo=False,
        pool_pre_ping=True,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        expire_on_commit=False,
        autoflush=False,
        class_=AsyncSession,
    )
    return _engine, _session_factory


class _LazySpiderAsyncSessionFactory:
    def __call__(self, *args, **kwargs):
        _, factory = _ensure_spider_engine()
        return factory(*args, **kwargs)


SpiderAsyncSessionFactory = _LazySpiderAsyncSessionFactory()


def get_spider_engine() -> AsyncEngine:
    """Get spider AsyncEngine (created lazily)."""
    engine, _ = _ensure_spider_engine()
    return engine


async def close_spider_engine() -> None:
    """Explicitly dispose spider engine/pool.

    Useful on Windows to avoid 'Event loop is closed' warnings at process exit.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
