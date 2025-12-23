# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 分析任务仓储

from __future__ import annotations

from typing import Dict, Any, Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.orm.analysis_job_orm import OpsAnalysisJobsORM


class AnalysisJobRepository:
    @staticmethod
    async def create(
            db: AsyncSession,
            *,
            job_type: int,
            payload: Dict[str, Any],
            created_by: int,
            spider_task_id: Optional[int] = None,
            trace: Optional[Dict[str, Any]] = None,
    ) -> OpsAnalysisJobsORM:
        row = OpsAnalysisJobsORM(
            job_type=job_type,
            status=10,
            payload=payload,
            created_by=created_by,
            spider_task_id=spider_task_id,
            trace=trace or {},
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    @staticmethod
    async def get_by_job_id(db: AsyncSession, *, job_id: int) -> Optional[OpsAnalysisJobsORM]:
        res = await db.execute(select(OpsAnalysisJobsORM).where(OpsAnalysisJobsORM.job_id == job_id))
        return res.scalar_one_or_none()

    @staticmethod
    async def list_jobs(
            db: AsyncSession,
            *,
            created_by: Optional[int] = None,
            job_type: Optional[int] = None,
            status: Optional[int] = None,
            limit: int = 50,
            offset: int = 0,
    ) -> List[OpsAnalysisJobsORM]:
        stmt = select(OpsAnalysisJobsORM)
        if created_by is not None:
            stmt = stmt.where(OpsAnalysisJobsORM.created_by == created_by)
        if job_type is not None:
            stmt = stmt.where(OpsAnalysisJobsORM.job_type == job_type)
        if status is not None:
            stmt = stmt.where(OpsAnalysisJobsORM.status == status)

        stmt = stmt.order_by(OpsAnalysisJobsORM.job_id.desc()).limit(limit).offset(offset)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def mark_ready(db: AsyncSession, *, job_id: int) -> None:
        await db.execute(update(OpsAnalysisJobsORM).where(OpsAnalysisJobsORM.job_id == job_id).values(status=15))

    @staticmethod
    async def mark_ready_by_spider_task_id(db: AsyncSession, *, spider_task_id: int) -> None:
        stmt = (
            update(OpsAnalysisJobsORM)
            .where(OpsAnalysisJobsORM.spider_task_id == spider_task_id)
            .where(OpsAnalysisJobsORM.status == 10)
            .values(status=15)
        )
        await db.execute(stmt)

    @staticmethod
    async def mark_running(db: AsyncSession, *, job_id: int) -> None:
        await db.execute(update(OpsAnalysisJobsORM).where(OpsAnalysisJobsORM.job_id == job_id).values(status=20))

    @staticmethod
    async def claim_one_ready(db: AsyncSession) -> Optional[OpsAnalysisJobsORM]:
        res = await db.execute(
            select(OpsAnalysisJobsORM).where(OpsAnalysisJobsORM.status == 15).order_by(
                OpsAnalysisJobsORM.job_id.asc()).limit(1)
        )
        job = res.scalar_one_or_none()
        if not job:
            return None

        upd = (
            update(OpsAnalysisJobsORM)
            .where(OpsAnalysisJobsORM.job_id == job.job_id)
            .where(OpsAnalysisJobsORM.status == 15)
            .values(status=20)
        )
        r = await db.execute(upd)
        if not r.rowcount:
            return None

        res2 = await db.execute(select(OpsAnalysisJobsORM).where(OpsAnalysisJobsORM.job_id == job.job_id))
        return res2.scalar_one_or_none()

    @staticmethod
    async def mark_done(db: AsyncSession, *, job_id: int, result: Dict[str, Any]) -> None:
        await db.execute(
            update(OpsAnalysisJobsORM)
            .where(OpsAnalysisJobsORM.job_id == job_id)
            .values(status=30, result=result, error_code="", error_message="")
        )

    @staticmethod
    async def mark_failed(db: AsyncSession, *, job_id: int, error_code: str, error_message: str) -> None:
        await db.execute(
            update(OpsAnalysisJobsORM)
            .where(OpsAnalysisJobsORM.job_id == job_id)
            .values(status=40, error_code=error_code, error_message=error_message)
        )

    @staticmethod
    async def mark_failed_by_spider_task_id(
            db: AsyncSession, *, spider_task_id: int, error_code: str, error_message: str
    ) -> None:
        stmt = (
            update(OpsAnalysisJobsORM)
            .where(OpsAnalysisJobsORM.spider_task_id == spider_task_id)
            .where(OpsAnalysisJobsORM.status.in_([10, 15, 20]))
            .values(status=40, error_code=error_code, error_message=error_message)
        )
        await db.execute(stmt)
