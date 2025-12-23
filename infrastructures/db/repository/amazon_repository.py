# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 亚马逊数据仓储（amazon_* 表读取）
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.orm.amazon_orm import (
    AmazonKeywordMetricORM,
    AmazonProductSnapshotORM,
    AmazonReviewORM,
)


class AmazonRepository:
    async def list_snapshots(self, db: AsyncSession, crawl_batch_no: int, site: str) -> List[AmazonProductSnapshotORM]:
        stmt = (
            select(AmazonProductSnapshotORM)
            .where(AmazonProductSnapshotORM.crawl_batch_no == crawl_batch_no)
            .where(AmazonProductSnapshotORM.site == site)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def list_reviews(
        self,
        db: AsyncSession,
        crawl_batch_no: int,
        site: str,
        asins: Optional[List[str]] = None,
    ) -> List[AmazonReviewORM]:
        stmt = (
            select(AmazonReviewORM)
            .where(AmazonReviewORM.crawl_batch_no == crawl_batch_no)
            .where(AmazonReviewORM.site == site)
        )
        if asins:
            stmt = stmt.where(AmazonReviewORM.asin.in_(asins))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def list_keyword_metrics(
        self,
        db: AsyncSession,
        crawl_batch_no: int,
        site: str,
        keywords: Optional[List[str]] = None,
    ) -> List[AmazonKeywordMetricORM]:
        stmt = (
            select(AmazonKeywordMetricORM)
            .where(AmazonKeywordMetricORM.crawl_batch_no == crawl_batch_no)
            .where(AmazonKeywordMetricORM.site == site)
        )
        if keywords:
            stmt = stmt.where(AmazonKeywordMetricORM.keyword.in_(keywords))
        res = await db.execute(stmt)
        return list(res.scalars().all())
