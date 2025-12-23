# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 众筹项目数据仓储（kickstarter/indiegogo/makuake）
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.orm.crowdfunding_orm import KickstarterProjectORM, MakuakeProjectORM, YsProjectORM


class CrowdfundingRepository:
    async def list_kickstarter_projects(
        self,
        db: AsyncSession,
        batch_no: Optional[int] = None,
        category_id: Optional[int] = None,
        limit: int = 200,
    ) -> List[KickstarterProjectORM]:
        stmt = select(KickstarterProjectORM)
        if batch_no is not None:
            stmt = stmt.where(KickstarterProjectORM.batch_no == batch_no)
        if category_id is not None:
            stmt = stmt.where(KickstarterProjectORM.category_id == category_id)
        stmt = stmt.limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def list_indiegogo_projects(
        self,
        db: AsyncSession,
        limit: int = 200,
    ) -> List[YsProjectORM]:
        stmt = select(YsProjectORM).where(YsProjectORM.source == "indiegogo").limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def list_makuake_projects(
        self,
        db: AsyncSession,
        batch_id: Optional[int] = None,
        limit: int = 200,
    ) -> List[MakuakeProjectORM]:
        stmt = select(MakuakeProjectORM)
        if batch_id is not None:
            stmt = stmt.where(MakuakeProjectORM.batch_id == batch_id)
        stmt = stmt.limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())
