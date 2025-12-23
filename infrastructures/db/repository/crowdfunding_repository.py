# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 众筹项目数据仓储

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.orm.crowdfunding_orm import SrcKickstarterProjectsORM, SrcProjectsORM, SrcMakuakeProjectsORM


class CrowdfundingRepository:
    @staticmethod
    async def list_kickstarter_projects(
            db: AsyncSession,
            batch_no: Optional[int] = None,
            category_id: Optional[int] = None,
            limit: int = 200,
    ) -> List[SrcKickstarterProjectsORM]:
        stmt = select(SrcKickstarterProjectsORM)
        if batch_no is not None:
            stmt = stmt.where(SrcKickstarterProjectsORM.batch_no == batch_no)
        if category_id is not None:
            stmt = stmt.where(SrcKickstarterProjectsORM.category_id == category_id)
        stmt = stmt.limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_indiegogo_projects(
            db: AsyncSession,
            limit: int = 200,
    ) -> List[SrcProjectsORM]:
        stmt = select(SrcProjectsORM).where(SrcProjectsORM.source == "indiegogo").limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_makuake_projects(
            db: AsyncSession,
            batch_id: Optional[int] = None,
            limit: int = 200,
    ) -> List[SrcMakuakeProjectsORM]:
        stmt = select(SrcMakuakeProjectsORM)
        if batch_id is not None:
            stmt = stmt.where(SrcMakuakeProjectsORM.batch_id == batch_id)
        stmt = stmt.limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())
