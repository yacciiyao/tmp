# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 用户表（认证与权限）

from __future__ import annotations

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructures.db.orm.orm_base import Base, TimestampMixin


class UserORM(TimestampMixin, Base):
    __tablename__ = "meta_users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="用户ID")

    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="用户名")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码哈希")

    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user", comment="角色：admin/user")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="状态：1启用/0停用")

    __table_args__ = (
        Index("ix_usr_uname", "username"),
        Index("ix_usr_role", "role"),
        Index("ix_usr_status", "status"),
    )
