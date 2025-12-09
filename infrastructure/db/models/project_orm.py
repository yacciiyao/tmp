# -*- coding: utf-8 -*-
# @File: project_orm.py
# @Author: yaccii
# @Time: 2025-12-07 10:15
# @Description:
from sqlalchemy import ForeignKey, String, Float, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.base import TimestampMixin, Base, int_pk


class ProjectORM(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int_pk]
    brand_id: Mapped[int | None] = mapped_column(
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    target_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    raised_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    tags: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    brand: Mapped["BrandORM"] = relationship()