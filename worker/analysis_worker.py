# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 分析任务Worker（不阻塞接口提交，异步生成报告）

from __future__ import annotations

import asyncio
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from domains.analysis_job_domain import AnalysisJobType
from infrastructures.db.orm.orm_base import AsyncSessionFactory
from infrastructures.vlogger import get_logger
from services.agents.amazon.amazon_report_generator import AmazonReportGenerator
from services.jobs.analysis_job_service import AnalysisJobService
from services.spider.spider_task_service import SpiderTaskService

logger = get_logger(__name__)


class AnalysisWorker:
    def __init__(self) -> None:
        self.session_factory = AsyncSessionFactory
        self.job_svc = AnalysisJobService()
        self.spider_svc = SpiderTaskService()
        self.amazon_gen = AmazonReportGenerator()

    async def run_forever(self, *, poll_seconds: int = 3) -> None:
        while True:
            async with self.session_factory() as db:
                job = await self.job_svc.claim_one_ready(db)
                if not job:
                    await db.commit()
                    await asyncio.sleep(poll_seconds)
                    continue

                try:
                    await self._process_one(db, job_id=job.job_id)
                    await db.commit()
                except Exception as e:
                    # 明确的业务兜底：避免worker整体退出
                    await self.job_svc.mark_failed(
                        db, job_id=job.job_id, error_code="ANALYSIS_FAILED", error_message=str(e)
                    )
                    await db.commit()
                    logger.exception("analysis job failed: job_id=%s", job.job_id)

    async def _process_one(self, db: AsyncSession, *, job_id: int) -> None:
        job = await self.job_svc.get_job(db, job_id=job_id)
        if not job:
            return

        if job.job_type == int(AnalysisJobType.AMAZON_MARKET_REPORT):
            await self._process_amazon_market_report(db, job)
            return

        await self.job_svc.mark_failed(
            db,
            job_id=job.job_id,
            error_code="NOT_IMPLEMENTED",
            error_message=f"job_type={job.job_type} 暂未实现",
        )

    async def _process_amazon_market_report(self, db: AsyncSession, job: Any) -> None:
        if not job.spider_task_id:
            await self.job_svc.mark_failed(
                db, job_id=job.job_id, error_code="NO_SPIDER_TASK", error_message="缺少 spider_task_id"
            )
            return

        spider_task = await self.spider_svc.get_task(db, task_id=job.spider_task_id)
        if not spider_task or spider_task.status != 30:
            await self.job_svc.mark_failed(
                db,
                job_id=job.job_id,
                error_code="SPIDER_NOT_READY",
                error_message="爬虫任务未就绪",
            )
            return

        locator: Dict[str, Any] = spider_task.result_locator or {}
        crawl_batch_no = locator.get("crawl_batch_no")
        if not isinstance(crawl_batch_no, int):
            await self.job_svc.mark_failed(
                db, job_id=job.job_id, error_code="BAD_LOCATOR", error_message="result_locator 缺少 crawl_batch_no"
            )
            return

        payload = job.payload or {}
        report = await self.amazon_gen.build_market_report(
            db,
            crawl_batch_no=crawl_batch_no,
            site=str(payload.get("site") or "us"),
            keyword=payload.get("keyword"),
            asin=payload.get("asin"),
            category=payload.get("category"),
            top_n=int(payload.get("top_n") or 10),
        )
        await self.job_svc.mark_done(db, job_id=job.job_id, result=report)
        logger.info("analysis job done: job_id=%s crawl_batch_no=%s", job.job_id, crawl_batch_no)
