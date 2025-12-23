# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 亚马逊市场报告任务提交（只负责提交，不阻塞等待爬虫结果）

from __future__ import annotations

import hashlib
import json
from typing import List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from domains.amazon_domain import AmazonMarketReportReq
from domains.analysis_job_domain import AnalysisJobType
from domains.error_domain import ValidationAppError
from infrastructures.db.orm.analysis_job_orm import OpsAnalysisJobsORM
from infrastructures.db.orm.spider_orm import OpsSpiderTasksORM
from services.jobs.analysis_job_service import AnalysisJobService
from services.spider.spider_task_service import SpiderTaskService


class AmazonMarketReportService:
    def __init__(self) -> None:
        self._spider_task_svc = SpiderTaskService()
        self._analysis_job_svc = AnalysisJobService()

    async def submit_market_report(
            self,
            db: AsyncSession,
            req: AmazonMarketReportReq,
            *,
            created_by: int,
    ) -> Tuple[OpsAnalysisJobsORM, OpsSpiderTasksORM]:
        """创建爬虫任务并生成分析任务（不等待爬虫结果）。"""
        if not (req.keyword or req.asin or req.category):
            raise ValidationAppError(
                message="keyword/asin/category 至少传一个",
                details=req.model_dump(),
            )

        task_key = self._build_task_key(req)
        result_tables = self._result_tables()

        spider_task = await self._spider_task_svc.create_task(
            db,
            task_type="amazon.collect",
            task_key=task_key,
            payload=req.model_dump(),
            biz="amazon",
            result_tables=result_tables,
            created_by=created_by,
        )
        await self._spider_task_svc.enqueue_task(db, spider_task)

        trace = {
            "spider_task_key": task_key,
            "result_tables": result_tables,
            "spider_task": {
                "task_id": int(spider_task.task_id),
                "task_type": str(spider_task.task_type),
                "task_key": str(spider_task.task_key),
                "status": int(spider_task.status),
            },
        }

        job = await self._analysis_job_svc.create_job(
            db,
            job_type=int(AnalysisJobType.AMAZON_MARKET_REPORT.value),
            payload=req.model_dump(),
            created_by=int(created_by),
            spider_task_id=int(spider_task.task_id),
            trace=trace,
        )

        return job, spider_task

    @staticmethod
    def _build_task_key(req: AmazonMarketReportReq) -> str:
        raw = json.dumps(req.model_dump(), ensure_ascii=False, sort_keys=True)
        md5 = hashlib.md5(raw.encode("utf-8")).hexdigest()
        return f"amazon:market_report:{md5}"

    @staticmethod
    def _result_tables() -> List[str]:
        return [
            "amazon_product_snapshots",
            "amazon_reviews",
            "amazon_keyword_metrics",
        ]
