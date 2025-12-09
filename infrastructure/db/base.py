# -*- coding: utf-8 -*-
# @File: base.py
# @Author: yaccii
# @Description:
from __future__ import annotations

import time

from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from infrastructure.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy Declarative 基类"""
    pass


def now_ts() -> int:
    return int(time.time())


class TimestampMixin:
    """
    通用时间戳混入：
    - created_at
    - updated_at
    """
    created_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=now_ts,
    )
    updated_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=now_ts,
        onupdate=now_ts,
    )


# ---------- 异步引擎 & SessionFactory ----------

engine: AsyncEngine = create_async_engine(
    settings.db_url,
    echo=False,        # 如需调试可改为 True
    pool_pre_ping=True,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_db() -> None:
    """
    创建所有 ORM 对应的数据表。

    注意：
    - 只建表，不建库。DB_URL 里的数据库（schema）需要提前在 MySQL 里建好。
    - 请在这里显式 import 所有 ORM 模块，确保 Base.metadata 收到所有映射。
    """
    # 用户/会话等原有表（保持不动）
    import infrastructure.db.models.user_orm  # noqa: F401
    import infrastructure.db.models.chat_orm  # noqa: F401

    # 其他业务表（如果已有的话，统一在这里导入）
    try:
        import infrastructure.db.models.agent_orm  # noqa: F401
    except ImportError:
        pass
    try:
        import infrastructure.db.models.brand_orm  # noqa: F401
    except ImportError:
        pass
    try:
        import infrastructure.db.models.project_orm  # noqa: F401
    except ImportError:
        pass
    try:
        import infrastructure.db.models.rag_orm  # noqa: F401
    except ImportError:
        pass

    # LLM 模型配置表（本次新增）
    import infrastructure.db.models.model_orm  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
