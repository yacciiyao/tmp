# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: ORM基类与数据库初始化

from __future__ import annotations

import time

from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from infrastructures.vconfig import vconfig


def now_ts() -> int:
    return int(time.time())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts, comment="创建时间(秒)")
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts, comment="更新时间(秒)"
    )


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_db_engine() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    global _engine, _session_factory
    if _engine is not None and _session_factory is not None:
        return _engine, _session_factory

    _engine = create_async_engine(
        str(vconfig.db_url),
        echo=bool(vconfig.sql_echo),
        pool_pre_ping=True,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        expire_on_commit=False,
        autoflush=False,
        class_=AsyncSession,
    )
    return _engine, _session_factory


class _LazyAsyncSessionFactory:
    def __call__(self, *args, **kwargs):
        _, factory = _ensure_db_engine()
        return factory(*args, **kwargs)


AsyncSessionFactory = _LazyAsyncSessionFactory()


async def init_db() -> None:
    from infrastructures.db.orm import user_orm  # noqa: F401
    from infrastructures.db.orm import rag_orm  # noqa: F401
    from infrastructures.db.orm import analysis_job_orm  # noqa: F401
    from infrastructures.db.orm import spider_orm  # noqa: F401
    from infrastructures.db.orm import amazon_orm  # noqa: F401
    from infrastructures.db.orm import brand_orm  # noqa: F401
    from infrastructures.db.orm import crowdfunding_orm  # noqa: F401

    engine, _ = _ensure_db_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
