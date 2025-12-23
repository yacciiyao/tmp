# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 品牌数据仓储

from __future__ import annotations

from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.orm.brand_orm import SrcBrandsORM, SrcBrandKeywordsORM, SrcBrandWebsitesORM, \
    SrcBrandAmazonDataORM, SrcBrandGoogleDataORM, SrcBrandSimilarwebDataORM


class BrandRepository:
    @staticmethod
    async def get_brand(db: AsyncSession, brand_id: int) -> Optional[SrcBrandsORM]:
        stmt = select(SrcBrandsORM).where(SrcBrandsORM.id == brand_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_keywords(db: AsyncSession, brand_id: int) -> List[SrcBrandKeywordsORM]:
        stmt = select(SrcBrandKeywordsORM).where(SrcBrandKeywordsORM.brand_id == brand_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_websites(db: AsyncSession, brand_id: int) -> List[SrcBrandWebsitesORM]:
        stmt = select(SrcBrandWebsitesORM).where(SrcBrandWebsitesORM.brand_id == brand_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_amazon_data(db: AsyncSession, brand_id: int) -> List[SrcBrandAmazonDataORM]:
        stmt = select(SrcBrandAmazonDataORM).where(SrcBrandAmazonDataORM.brand_id == brand_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_google_data(db: AsyncSession, brand_id: int) -> List[SrcBrandGoogleDataORM]:
        stmt = select(SrcBrandGoogleDataORM).where(SrcBrandGoogleDataORM.brand_id == brand_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_independence_data(db: AsyncSession, brand_id: int) -> List[SrcBrandSimilarwebDataORM]:
        stmt = select(SrcBrandSimilarwebDataORM).where(SrcBrandSimilarwebDataORM.brand_id == brand_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())
