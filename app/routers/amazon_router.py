# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 亚马逊运营相关接口（任务提交）

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from domains.amazon_domain import AmazonMarketReportReq
from domains.analysis_job_domain import AnalysisJobVO
from infrastructures.db.orm.analysis_job_orm import AnalysisJobORM
from infrastructures.db.orm.user_orm import UserORM
from services.agents.amazon.market_report_service import AmazonMarketReportService

router = APIRouter(prefix="/amazon", tags=["amazon"])

_svc = AmazonMarketReportService()


class AmazonMarketReportSubmitResp(BaseModel):
    job: AnalysisJobVO


def _job_to_vo(job: AnalysisJobORM) -> AnalysisJobVO:
    return AnalysisJobVO(
        job_id=int(job.job_id),
        job_type=int(job.job_type),
        status=int(job.status),
        payload=job.payload or {},
        trace=job.trace or {},
        result=job.result or {},
        error_code=job.error_code or "",
        error_message=job.error_message or "",
        created_by=int(job.created_by or 0),
        spider_task_id=int(job.spider_task_id) if job.spider_task_id is not None else None,
        created_at=int(job.created_at or 0),
        updated_at=int(job.updated_at or 0),
    )


@router.post("/market-report", response_model=AmazonMarketReportSubmitResp)
async def submit_market_report(
    req: AmazonMarketReportReq,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
) -> AmazonMarketReportSubmitResp:
    job, _spider_task = await _svc.submit_market_report(db, req, created_by=current_user.user_id)
    return AmazonMarketReportSubmitResp(job=_job_to_vo(job))
