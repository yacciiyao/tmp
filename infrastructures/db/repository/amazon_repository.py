# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 亚马逊数据仓储（只读；提供确定性筛选/排序/分页，避免一次性拉爆内存；兼容 MySQL 排序语法）

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.orm.amazon_orm import (
    SrcAmazonKeywordMetricsORM,
    SrcAmazonProductSnapshotsORM,
    SrcAmazonReviewsORM,
)


class AmazonRepository:
    @staticmethod
    async def list_snapshots(
            db: AsyncSession,
            *,
            crawl_batch_no: int,
            site: str,
            limit: int = 200,
            offset: int = 0,
            asins: Optional[List[str]] = None,
            category_contains: Optional[str] = None,
            price_min: Optional[float] = None,
            price_max: Optional[float] = None,
    ) -> List[SrcAmazonProductSnapshotsORM]:
        stmt = (
            select(SrcAmazonProductSnapshotsORM)
            .where(SrcAmazonProductSnapshotsORM.crawl_batch_no == crawl_batch_no)
            .where(SrcAmazonProductSnapshotsORM.site == site)
        )

        if asins:
            stmt = stmt.where(SrcAmazonProductSnapshotsORM.asin.in_(asins))
        if category_contains:
            stmt = stmt.where(SrcAmazonProductSnapshotsORM.category.ilike(f"%{category_contains}%"))
        if price_min is not None:
            stmt = stmt.where(SrcAmazonProductSnapshotsORM.price >= price_min)
        if price_max is not None:
            stmt = stmt.where(SrcAmazonProductSnapshotsORM.price <= price_max)

        stmt = (
            stmt.order_by(
                (SrcAmazonProductSnapshotsORM.review_count.is_(None)).asc(),
                desc(SrcAmazonProductSnapshotsORM.review_count),
                (SrcAmazonProductSnapshotsORM.rating.is_(None)).asc(),
                desc(SrcAmazonProductSnapshotsORM.rating),
                SrcAmazonProductSnapshotsORM.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_reviews(
            db: AsyncSession,
            *,
            crawl_batch_no: int,
            site: str,
            limit: int = 1000,
            offset: int = 0,
            asins: Optional[List[str]] = None,
    ) -> List[SrcAmazonReviewsORM]:
        stmt = (
            select(SrcAmazonReviewsORM)
            .where(SrcAmazonReviewsORM.crawl_batch_no == crawl_batch_no)
            .where(SrcAmazonReviewsORM.site == site)
        )

        if asins:
            stmt = stmt.where(SrcAmazonReviewsORM.asin.in_(asins))

        stmt = (
            stmt.order_by(
                (SrcAmazonReviewsORM.review_time.is_(None)).asc(),
                desc(SrcAmazonReviewsORM.review_time),
                (SrcAmazonReviewsORM.helpful_count.is_(None)).asc(),
                desc(SrcAmazonReviewsORM.helpful_count),
                SrcAmazonReviewsORM.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_keyword_metrics(
            db: AsyncSession,
            *,
            crawl_batch_no: int,
            site: str,
            limit: int = 800,
            offset: int = 0,
            keywords: Optional[List[str]] = None,
    ) -> List[SrcAmazonKeywordMetricsORM]:
        stmt = (
            select(SrcAmazonKeywordMetricsORM)
            .where(SrcAmazonKeywordMetricsORM.crawl_batch_no == crawl_batch_no)
            .where(SrcAmazonKeywordMetricsORM.site == site)
        )

        if keywords:
            stmt = stmt.where(SrcAmazonKeywordMetricsORM.keyword.in_(keywords))

        stmt = (
            stmt.order_by(
                (SrcAmazonKeywordMetricsORM.search_volume.is_(None)).asc(),
                desc(SrcAmazonKeywordMetricsORM.search_volume),
                SrcAmazonKeywordMetricsORM.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        res = await db.execute(stmt)
        return list(res.scalars().all())
