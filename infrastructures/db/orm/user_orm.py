# -*- coding: utf-8 -*-
# @File: user_orm.py

from __future__ import annotations

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructures.db.orm.orm_base import Base, TimestampMixin


class UserORM(TimestampMixin, Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_users_username", "username"),
        Index("ix_users_status", "status"),
        Index("ix_users_role", "role"),
    )
