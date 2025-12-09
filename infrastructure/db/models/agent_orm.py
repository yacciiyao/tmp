# -*- coding: utf-8 -*-
# @File: agent_orm.py
# @Author: yaccii
# @Time: 2025-12-07 10:15
# @Description:
from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base, TimestampMixin, int_pk


class AgentORM(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[int_pk]
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    type: Mapped[str] = mapped_column(String(32))  # 对应 AgentType 的字符串
    default_model_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
