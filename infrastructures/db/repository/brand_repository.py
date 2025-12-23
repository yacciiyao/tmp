# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 品牌数据仓储（ys_brand* 表读取）
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.orm.brand_orm import (
    YsBrandAmazonDataORM,
    YsBrandGoogleDataORM,
    YsBrandIndependenceDataORM,
    YsBrandKeywordORM,
    YsBrandORM,
    YsBrandWebsiteORM,
)


class BrandRepository:
    async def get_brand(self, db: AsyncSession, brand_id: int) -> Optional[YsBrandORM]:
        stmt = select(YsBrandORM).where(YsBrandORM.id == brand_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_keywords(self, db: AsyncSession, brand_id: int) -> List[YsBrandKeywordORM]:
        stmt = select(YsBrandKeywordORM).where(YsBrandKeywordORM.brand_id == brand_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def list_websites(self, db: AsyncSession, brand_id: int) -> List[YsBrandWebsiteORM]:
        stmt = select(YsBrandWebsiteORM).where(YsBrandWebsiteORM.brand_id == brand_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def list_amazon_data(self, db: AsyncSession, brand_id: int) -> List[YsBrandAmazonDataORM]:
        stmt = select(YsBrandAmazonDataORM).where(YsBrandAmazonDataORM.brand_id == brand_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def list_google_data(self, db: AsyncSession, brand_id: int) -> List[YsBrandGoogleDataORM]:
        stmt = select(YsBrandGoogleDataORM).where(YsBrandGoogleDataORM.brand_id == brand_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def list_independence_data(self, db: AsyncSession, brand_id: int) -> List[YsBrandIndependenceDataORM]:
        stmt = select(YsBrandIndependenceDataORM).where(YsBrandIndependenceDataORM.brand_id == brand_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())
