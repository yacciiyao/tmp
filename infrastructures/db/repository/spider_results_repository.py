# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Read-only repository for spider(results) DB.

from __future__ import annotations

from typing import List, Optional, Iterable

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.spider_orm.spider_results_orm import (
    SpiderRunsORM,
    AmazonReviewItemsORM,
    AmazonReviewMediaORM,
)


def _chunked(ids: Iterable[int], chunk_size: int) -> List[List[int]]:
    buf: List[int] = []
    out: List[List[int]] = []
    for x in ids:
        buf.append(int(x))
        if len(buf) >= chunk_size:
            out.append(buf)
            buf = []
    if buf:
        out.append(buf)
    return out


class SpiderResultsRepository:
    """Read-only accessors for spider(results) DB.

    Notes:
        - CRUD only: only reads are allowed.
        - Keep result shapes stable for downstream VOC analysis.
    """

    @staticmethod
    async def get_run(db: AsyncSession, *, run_id: int) -> Optional[SpiderRunsORM]:
        stmt = select(SpiderRunsORM).where(SpiderRunsORM.run_id == int(run_id))
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def count_reviews_by_run(db: AsyncSession, *, run_id: int) -> int:
        stmt = select(func.count()).select_from(AmazonReviewItemsORM).where(AmazonReviewItemsORM.run_id == int(run_id))
        res = await db.execute(stmt)
        return int(res.scalar_one() or 0)

    @staticmethod
    async def list_reviews_by_run(
        db: AsyncSession,
        *,
        run_id: int,
        limit: int = 1000,
        offset: int = 0,
        order_by_position: bool = True,
    ) -> List[AmazonReviewItemsORM]:
        stmt = select(AmazonReviewItemsORM).where(AmazonReviewItemsORM.run_id == int(run_id))
        if order_by_position:
            stmt = stmt.order_by(AmazonReviewItemsORM.page_num.asc(), AmazonReviewItemsORM.position.asc())
        else:
            stmt = stmt.order_by(AmazonReviewItemsORM.item_id.asc())

        stmt = stmt.limit(int(limit)).offset(int(offset))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def iter_reviews_by_run(
        db: AsyncSession,
        *,
        run_id: int,
        batch_size: int = 1000,
        order_by_position: bool = True,
    ):
        """Async generator yielding review batches.

        Intended for large runs (avoid loading all reviews into memory).
        """
        offset = 0
        while True:
            batch = await SpiderResultsRepository.list_reviews_by_run(
                db,
                run_id=int(run_id),
                limit=int(batch_size),
                offset=int(offset),
                order_by_position=order_by_position,
            )
            if not batch:
                break
            yield batch
            offset += len(batch)

    @staticmethod
    async def list_review_media(
        db: AsyncSession,
        *,
        review_item_ids: List[int],
        chunk_size: int = 500,
    ) -> List[AmazonReviewMediaORM]:
        if not review_item_ids:
            return []

        out: List[AmazonReviewMediaORM] = []
        for chunk in _chunked(review_item_ids, int(chunk_size)):
            stmt = (
                select(AmazonReviewMediaORM)
                .where(AmazonReviewMediaORM.review_item_id.in_(chunk))
                .order_by(AmazonReviewMediaORM.review_item_id.asc(), AmazonReviewMediaORM.sort.asc())
            )
            res = await db.execute(stmt)
            out.extend(list(res.scalars().all()))
        return out
