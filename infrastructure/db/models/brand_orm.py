# -*- coding: utf-8 -*-
# @File: brand_orm.py
# @Author: yaccii
# @Time: 2025-12-07 10:15
# @Description:
from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import TimestampMixin, Base, int_pk


class BrandORM(TimestampMixin, Base):
    __tablename__ = "brands"

    id: Mapped[int_pk]
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    slug: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)