# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 亚马逊数据仓储

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.orm.amazon_orm import SrcAmazonProductSnapshotsORM, SrcAmazonReviewsORM, \
    SrcAmazonKeywordMetricsORM


class AmazonRepository:
    @staticmethod
    async def list_snapshots(db: AsyncSession, crawl_batch_no: int, site: str) -> List[SrcAmazonProductSnapshotsORM]:
        stmt = (
            select(SrcAmazonProductSnapshotsORM)
            .where(SrcAmazonProductSnapshotsORM.crawl_batch_no == crawl_batch_no)
            .where(SrcAmazonProductSnapshotsORM.site == site)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_reviews(
            db: AsyncSession,
            crawl_batch_no: int,
            site: str,
            asins: Optional[List[str]] = None,
    ) -> List[SrcAmazonReviewsORM]:
        stmt = (
            select(SrcAmazonReviewsORM)
            .where(SrcAmazonReviewsORM.crawl_batch_no == crawl_batch_no)
            .where(SrcAmazonReviewsORM.site == site)
        )
        if asins:
            stmt = stmt.where(SrcAmazonReviewsORM.asin.in_(asins))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_keyword_metrics(
            db: AsyncSession,
            crawl_batch_no: int,
            site: str,
            keywords: Optional[List[str]] = None,
    ) -> List[SrcAmazonKeywordMetricsORM]:
        stmt = (
            select(SrcAmazonKeywordMetricsORM)
            .where(SrcAmazonKeywordMetricsORM.crawl_batch_no == crawl_batch_no)
            .where(SrcAmazonKeywordMetricsORM.site == site)
        )
        if keywords:
            stmt = stmt.where(SrcAmazonKeywordMetricsORM.keyword.in_(keywords))
        res = await db.execute(stmt)
        return list(res.scalars().all())
