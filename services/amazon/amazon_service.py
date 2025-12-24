# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Amazon 运营助手任务提交服务（创建 spider_task + analysis_job，不等待爬虫结果）

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Tuple, Union

from sqlalchemy.ext.asyncio import AsyncSession

from domains.amazon_domain import (
    AmazonCompetitorMatrixReq,
    AmazonListingAuditReq,
    AmazonMarketResearchReq,
    AmazonOpportunityScanReq,
    AmazonProductImprovementReq,
    AmazonReviewVocReq,
    AmazonTaskKind,
)
from domains.analysis_job_domain import AnalysisJobType
from domains.error_domain import ValidationAppError
from infrastructures.db.orm.analysis_job_orm import OpsAnalysisJobsORM
from infrastructures.vlogger import vlogger
from services.jobs.analysis_job_service import AnalysisJobService
from services.spider.spider_task_service import SpiderTaskService


AmazonOperationReq = Union[
    AmazonOpportunityScanReq,
    AmazonMarketResearchReq,
    AmazonCompetitorMatrixReq,
    AmazonListingAuditReq,
    AmazonReviewVocReq,
    AmazonProductImprovementReq,
]


class AmazonOperationService:
    """Amazon 运营助手任务提交：

    - 只负责创建 spider_task + analysis_job
    - 不等待爬虫结果（接口提交即返回 job_id / task_id）
    """

    def __init__(self) -> None:
        self._spider_svc = SpiderTaskService()
        self._job_svc = AnalysisJobService()

    async def submit(
            self,
            db: AsyncSession,
            req: AmazonOperationReq,
            *,
            created_by: int,
    ) -> Tuple[OpsAnalysisJobsORM, int]:
        """提交 Amazon 分析任务。

        返回： (analysis_job, spider_task_id)
        """
        task_kind = str(getattr(req, "task_kind", ""))
        if task_kind not in (
                AmazonTaskKind.AOA_01,
                AmazonTaskKind.AOA_02,
                AmazonTaskKind.AOA_03,
                AmazonTaskKind.AOA_04,
                AmazonTaskKind.AOA_05,
                AmazonTaskKind.AOA_06,
        ):
            raise ValidationAppError(message="invalid task_kind", details={"task_kind": task_kind})

        spider_payload = self._build_spider_payload(req)
        task_key = self._build_task_key(task_kind=task_kind, spider_payload=spider_payload)
        result_tables = self._result_tables(task_kind)

        # 幂等：优先复用同 task_key 的爬虫任务，避免重复爬取/unique 冲突
        spider_task = await self._spider_svc.get_by_key(db, task_key=task_key)
        if spider_task is None:
            spider_task = await self._spider_svc.create_task(
                db,
                task_type="amazon.collect",
                task_key=task_key,
                biz="amazon",
                payload=spider_payload,
                result_tables=result_tables,
                created_by=int(created_by),
            )

        # 若状态为 CREATED 则推进入队；否则无副作用
        await self._spider_svc.enqueue_task(db, spider_task)

        trace: Dict[str, Any] = {
            "schema_version": "v1",
            "biz": "amazon",
            "task_kind": task_kind,
            "spider_task_key": task_key,
            "result_tables": result_tables,
            "spider_task": {
                "task_id": int(spider_task.task_id),
                "task_type": str(spider_task.task_type),
                "task_key": str(spider_task.task_key),
                "status": int(spider_task.status),
            },
            "request_id": req.request_id,
        }

        job_payload = {
            "biz": "amazon",
            "task_kind": task_kind,
            "req": req.model_dump(mode="json"),
        }

        job = await self._job_svc.create_job(
            db,
            job_type=int(AnalysisJobType.AMAZON_OPERATION),
            payload=job_payload,
            created_by=int(created_by),
            spider_task_id=int(spider_task.task_id),
            trace=trace,
        )

        vlogger.info(
            "amazon.submit job_id=%s task_kind=%s spider_task_id=%s task_key=%s request_id=%s",
            int(job.job_id),
            task_kind,
            int(spider_task.task_id),
            task_key,
            req.request_id or "-",
        )
        return job, int(spider_task.task_id)

    @staticmethod
    def _build_spider_payload(req: AmazonOperationReq) -> Dict[str, Any]:
        """构建发送给爬虫的 payload（只包含影响爬取结果的字段）。

        约束：
        - payload 必须稳定可序列化（用于 task_key 幂等）
        - extra_notes 属于分析偏好，不影响爬虫结果，禁止进入 payload（否则破坏幂等）
        """
        return {
            "site": str(req.site),
            "task_kind": str(req.task_kind),
            "time_window": req.time_window.model_dump(mode="json"),
            "filters": req.filters.model_dump(mode="json"),
            "query": req.query.model_dump(mode="json"),
        }

    @staticmethod
    def _build_task_key(*, task_kind: str, spider_payload: Dict[str, Any]) -> str:
        raw = json.dumps({"task_kind": task_kind, "payload": spider_payload}, ensure_ascii=False, sort_keys=True)
        sha1 = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        return f"amazon:{task_kind}:{sha1}"

    @staticmethod
    def _result_tables(task_kind: str) -> List[str]:
        # 目前统一抓取三类源数据：快照/评论/关键词指标
        # 后续若需降本提速，可按 task_kind 细分，但不改表名与协议。
        _ = task_kind
        return [
            "src_amazon_product_snapshots",
            "src_amazon_reviews",
            "src_amazon_keyword_metrics",
        ]
