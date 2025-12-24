# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 分析任务Worker（不阻塞接口提交，异步生成报告）

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domains.analysis_job_domain import AnalysisJobType
from domains.error_domain import AppError
from infrastructures.db.orm.orm_base import AsyncSessionFactory
from infrastructures.vlogger import vlogger
from services.amazon.amazon_workflow import AmazonWorkflow
from services.jobs.analysis_job_service import AnalysisJobService


class AnalysisWorker:
    def __init__(self) -> None:
        self.session_factory = AsyncSessionFactory
        self.job_svc = AnalysisJobService()
        self.amazon_workflow = AmazonWorkflow()

    async def run_forever(self, *, poll_seconds: int = 3) -> None:
        while True:
            async with self.session_factory() as db:
                job = await self.job_svc.claim_one_ready(db)
                if not job:
                    await db.commit()
                    await asyncio.sleep(poll_seconds)
                    continue

                try:
                    await self._process_one(db, job_id=int(job.job_id))
                    await db.commit()
                except AppError as e:
                    await self.job_svc.mark_failed(db, job_id=int(job.job_id), error_code=e.code, error_message=e.message)
                    await db.commit()
                    vlogger.exception("analysis job failed(app_error): job_id=%s code=%s", job.job_id, e.code)
                except Exception as e:
                    await self.job_svc.mark_failed(
                        db, job_id=int(job.job_id), error_code="ANALYSIS_FAILED", error_message=str(e)
                    )
                    await db.commit()
                    vlogger.exception("analysis job failed: job_id=%s", job.job_id)

    async def _process_one(self, db: AsyncSession, *, job_id: int) -> None:
        job = await self.job_svc.get_job(db, job_id=job_id)
        if not job:
            return

        if int(job.job_type) == int(AnalysisJobType.AMAZON_OPERATION):
            await self._process_amazon_operation(db, job)
            return

        raise AppError(
            code="job.not_implemented",
            message=f"job_type={job.job_type} 暂未实现",
            http_status=500,
            details={"job_id": int(job.job_id)},
        )

    async def _process_amazon_operation(self, db: AsyncSession, job: Any) -> None:
        result = await self.amazon_workflow.run(db, job=job)
        await self.job_svc.mark_done(db, job_id=int(job.job_id), result=result)
        vlogger.info("analysis job done: job_id=%s", job.job_id)
