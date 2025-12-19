# -*- coding: utf-8 -*-
from __future__ import annotations

import time

from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from infrastructures.vconfig import config


def now_ts() -> int:
    return int(time.time())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts, comment="创建时间(秒)")
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ts, onupdate=now_ts, comment="更新时间(秒)"
    )


engine: AsyncEngine = create_async_engine(
    str(config.db_url),
    echo=bool(config.sql_echo),
    pool_pre_ping=True,
)

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    class_=AsyncSession,
)


async def init_db() -> None:
    from infrastructures.db.orm import user_orm  # noqa: F401
    from infrastructures.db.orm import rag_orm  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
