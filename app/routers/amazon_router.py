# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Amazon 运营助手接口（仅提交任务，不等待爬虫/分析结果）

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user
from domains.amazon_domain import (
    AmazonCompetitorMatrixReq,
    AmazonListingAuditReq,
    AmazonMarketResearchReq,
    AmazonOpportunityScanReq,
    AmazonProductImprovementReq,
    AmazonReviewVocReq,
)
from domains.analysis_job_domain import AnalysisJobVO
from infrastructures.db.orm.analysis_job_orm import OpsAnalysisJobsORM
from infrastructures.db.orm.orm_deps import get_db
from infrastructures.db.orm.user_orm import MetaUsersORM
from services.amazon.amazon_service import AmazonOperationService


router = APIRouter(prefix="/amazon", tags=["amazon"])

_svc = AmazonOperationService()


class AmazonSubmitResp(BaseModel):
    job: AnalysisJobVO


def _job_to_vo(job: OpsAnalysisJobsORM) -> AnalysisJobVO:
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


@router.post("/opportunity-scan", response_model=AmazonSubmitResp)
async def submit_opportunity_scan(
        req: AmazonOpportunityScanReq,
        db: AsyncSession = Depends(get_db),
        current_user: MetaUsersORM = Depends(get_current_user),
) -> AmazonSubmitResp:
    job, _ = await _svc.submit(db, req, created_by=int(current_user.user_id))
    return AmazonSubmitResp(job=_job_to_vo(job))


@router.post("/market-research", response_model=AmazonSubmitResp)
async def submit_market_research(
        req: AmazonMarketResearchReq,
        db: AsyncSession = Depends(get_db),
        current_user: MetaUsersORM = Depends(get_current_user),
) -> AmazonSubmitResp:
    job, _ = await _svc.submit(db, req, created_by=int(current_user.user_id))
    return AmazonSubmitResp(job=_job_to_vo(job))


@router.post("/competitor-matrix", response_model=AmazonSubmitResp)
async def submit_competitor_matrix(
        req: AmazonCompetitorMatrixReq,
        db: AsyncSession = Depends(get_db),
        current_user: MetaUsersORM = Depends(get_current_user),
) -> AmazonSubmitResp:
    job, _ = await _svc.submit(db, req, created_by=int(current_user.user_id))
    return AmazonSubmitResp(job=_job_to_vo(job))


@router.post("/listing-audit", response_model=AmazonSubmitResp)
async def submit_listing_audit(
        req: AmazonListingAuditReq,
        db: AsyncSession = Depends(get_db),
        current_user: MetaUsersORM = Depends(get_current_user),
) -> AmazonSubmitResp:
    job, _ = await _svc.submit(db, req, created_by=int(current_user.user_id))
    return AmazonSubmitResp(job=_job_to_vo(job))


@router.post("/review-voc", response_model=AmazonSubmitResp)
async def submit_review_voc(
        req: AmazonReviewVocReq,
        db: AsyncSession = Depends(get_db),
        current_user: MetaUsersORM = Depends(get_current_user),
) -> AmazonSubmitResp:
    job, _ = await _svc.submit(db, req, created_by=int(current_user.user_id))
    return AmazonSubmitResp(job=_job_to_vo(job))


@router.post("/product-improvement", response_model=AmazonSubmitResp)
async def submit_product_improvement(
        req: AmazonProductImprovementReq,
        db: AsyncSession = Depends(get_db),
        current_user: MetaUsersORM = Depends(get_current_user),
) -> AmazonSubmitResp:
    job, _ = await _svc.submit(db, req, created_by=int(current_user.user_id))
    return AmazonSubmitResp(job=_job_to_vo(job))
