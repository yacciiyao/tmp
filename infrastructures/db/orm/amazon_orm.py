# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Amazon 爬虫结构化源数据表 ORM（src_*；本项目只读分析）

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Float, Integer, JSON, Numeric, String, Text, UniqueConstraint, Index
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from infrastructures.db.orm.orm_base import Base, TimestampMixin


class SrcAmazonProductSnapshotsORM(TimestampMixin, Base):
    __tablename__ = "src_amazon_product_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="ID(自增)")
    crawl_batch_no: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="爬取批次号")

    site: Mapped[str] = mapped_column(String(8), nullable=False, comment="站点")
    asin: Mapped[str] = mapped_column(String(32), nullable=False, comment="ASIN")

    title: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="标题")
    brand: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="品牌")
    category: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="类目路径")

    price: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True, comment="价格")
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True, comment="币种")

    rating: Mapped[float | None] = mapped_column(Float, nullable=True, comment="评分")
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="评论数")

    bullet_points: Mapped[str | None] = mapped_column(Text, nullable=True, comment="五点描述（原始文本）")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="详情描述（原始文本）")
    attributes: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
        comment="关键属性（结构化/可扩展）",
    )

    url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="商品链接")
    crawl_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="爬取时间(秒)")

    __table_args__ = (
        UniqueConstraint("crawl_batch_no", "site", "asin", name="uq_amz_ps_bsa"),
        Index("ix_amz_ps_bs", "crawl_batch_no", "site"),
        Index("ix_amz_ps_asin", "asin"),
    )


class SrcAmazonReviewsORM(TimestampMixin, Base):
    __tablename__ = "src_amazon_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="ID(自增)")
    crawl_batch_no: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="爬取批次号")

    site: Mapped[str] = mapped_column(String(8), nullable=False, comment="站点")
    asin: Mapped[str] = mapped_column(String(32), nullable=False, comment="ASIN")
    review_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="评论ID（如有）")

    rating: Mapped[float | None] = mapped_column(Float, nullable=True, comment="星级")
    title: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="标题")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="正文")

    author: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="作者")
    verified: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="是否已验证购买：1是/0否")
    helpful_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="有用数")

    review_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="评论时间(秒)")
    raw: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
        comment="原始结构（可扩展）",
    )

    __table_args__ = (
        Index("ix_amz_rv_bs", "crawl_batch_no", "site"),
        Index("ix_amz_rv_asin", "asin"),
        Index("ix_amz_rv_rid", "review_id"),
    )


class SrcAmazonKeywordMetricsORM(TimestampMixin, Base):
    __tablename__ = "src_amazon_keyword_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="ID(自增)")
    crawl_batch_no: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="爬取批次号")

    site: Mapped[str] = mapped_column(String(8), nullable=False, comment="站点")
    keyword: Mapped[str] = mapped_column(String(255), nullable=False, comment="关键词")

    search_volume: Mapped[float | None] = mapped_column(Float, nullable=True, comment="搜索量")
    cpc: Mapped[float | None] = mapped_column(Float, nullable=True, comment="CPC")
    competition: Mapped[float | None] = mapped_column(Float, nullable=True, comment="竞争度（0-1）")

    raw: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
        comment="原始结构（可扩展）",
    )

    __table_args__ = (
        UniqueConstraint("crawl_batch_no", "site", "keyword", name="uq_amz_kw_bsk"),
        Index("ix_amz_kw_bs", "crawl_batch_no", "site"),
        Index("ix_amz_kw_kw", "keyword"),
    )
