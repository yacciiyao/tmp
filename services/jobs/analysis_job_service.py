# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 分析任务服务（创建/查询/状态流转）

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.orm.analysis_job_orm import OpsAnalysisJobsORM
from infrastructures.db.repository.analysis_job_repository import AnalysisJobRepository


class AnalysisJobService:
    def __init__(self) -> None:
        self.repo = AnalysisJobRepository()

    async def create_job(
            self,
            db: AsyncSession,
            *,
            job_type: int,
            payload: Dict[str, Any],
            created_by: int,
            spider_task_id: Optional[int] = None,
            trace: Optional[Dict[str, Any]] = None,
    ) -> OpsAnalysisJobsORM:
        return await self.repo.create(
            db,
            job_type=job_type,
            payload=payload,
            created_by=created_by,
            spider_task_id=spider_task_id,
            trace=trace,
        )

    async def get_job(self, db: AsyncSession, *, job_id: int) -> Optional[OpsAnalysisJobsORM]:
        return await self.repo.get_by_job_id(db, job_id=job_id)

    async def list_jobs(
            self,
            db: AsyncSession,
            *,
            created_by: Optional[int] = None,
            job_type: Optional[int] = None,
            status: Optional[int] = None,
            limit: int = 50,
            offset: int = 0,
    ) -> List[OpsAnalysisJobsORM]:
        return await self.repo.list_jobs(
            db,
            created_by=created_by,
            job_type=job_type,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def mark_ready(self, db: AsyncSession, *, job_id: int) -> None:
        await self.repo.mark_ready(db, job_id=job_id)

    async def mark_ready_by_spider_task_id(self, db: AsyncSession, *, spider_task_id: int) -> None:
        await self.repo.mark_ready_by_spider_task_id(db, spider_task_id=spider_task_id)

    async def mark_failed_by_spider_task_id(
            self, db: AsyncSession, *, spider_task_id: int, error_code: str, error_message: str
    ) -> None:
        await self.repo.mark_failed_by_spider_task_id(
            db, spider_task_id=spider_task_id, error_code=error_code, error_message=error_message
        )

    async def claim_one_ready(self, db: AsyncSession) -> Optional[OpsAnalysisJobsORM]:
        return await self.repo.claim_one_ready(db)

    async def mark_done(self, db: AsyncSession, *, job_id: int, result: Dict[str, Any]) -> None:
        await self.repo.mark_done(db, job_id=job_id, result=result)

    async def mark_failed(self, db: AsyncSession, *, job_id: int, error_code: str, error_message: str) -> None:
        await self.repo.mark_failed(db, job_id=job_id, error_code=error_code, error_message=error_message)
