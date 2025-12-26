# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC endpoints (v1): create review-analysis job + spider callback.

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_admin
from domains.error_domain import AppError
from domains.voc_domain import (
    VocCreateJobResponse,
    VocCreateReviewAnalysisJobRequest,
    VocJobResponse,
    VocSpiderCallbackResponse,
    VocSpiderCallbackRequest,
)
from domains.voc_review_domain import ReviewAnalysisReport

from infrastructures.db.orm.orm_deps import get_db
from infrastructures.db.repository.voc_repository import VocRepository
from services.voc.voc_service import VocService


router = APIRouter(prefix="/voc", tags=["voc"])


def _service() -> VocService:
    # No global singleton; create per request.
    return VocService(repo=VocRepository())


@router.post("/review-analysis/jobs", response_model=VocCreateJobResponse, summary="Create Review Analysis job")
async def create_review_analysis_job(
    body: VocCreateReviewAnalysisJobRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
) -> VocCreateJobResponse:
    job_id, status, report_id = await _service().create_review_analysis_job(
        db,
        site_code=body.site_code,
        asin=body.asin,
        created_by_user_id=int(admin.user_id),
    )
    return VocCreateJobResponse(job_id=job_id, status=status, report_id=report_id)


# Compatibility alias: user asked for /voc/job before.
@router.post("/job", response_model=VocCreateJobResponse, summary="Create VOC job (v1: Review Analysis)")
async def create_voc_job_alias(
    body: VocCreateReviewAnalysisJobRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
) -> VocCreateJobResponse:
    return await create_review_analysis_job(body=body, db=db, admin=admin)


@router.get("/jobs/{job_id}", response_model=VocJobResponse, summary="Get VOC job")
async def get_voc_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> VocJobResponse:
    job = await _service().get_job(db, job_id=int(job_id))
    if job is None:
        raise AppError(code="voc.job_not_found", message="Job not found", http_status=404, details={"job_id": job_id})
    return VocJobResponse.model_validate(job)


@router.post("/spider/callback", response_model=VocSpiderCallbackResponse, summary="Spider callback")
async def spider_callback(
    body: VocSpiderCallbackRequest,
    db: AsyncSession = Depends(get_db),
) -> VocSpiderCallbackResponse:
    updated_task_rows, updated_job_rows = await _service().handle_spider_callback(
        db,
        task_id=body.task_id,
        status_text=body.status,
        run_id=body.run_id,
        error=body.error,
        callback_token=body.callback_token,
    )
    return VocSpiderCallbackResponse(updated_task_rows=updated_task_rows, updated_job_rows=updated_job_rows)


@router.get("/reports/{report_id}", response_model=ReviewAnalysisReport, summary="Get VOC report")
async def get_voc_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> ReviewAnalysisReport:
    report = await _service().get_report(db, report_id=int(report_id))
    if report is None:
        raise AppError(
            code="voc.report_not_found",
            message="Report not found",
            http_status=404,
            details={"report_id": int(report_id)},
        )
    return ReviewAnalysisReport.model_validate(report.payload_json)


@router.get("/jobs/{job_id}/report", response_model=ReviewAnalysisReport, summary="Get VOC report by job")
async def get_voc_report_by_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> ReviewAnalysisReport:
    report = await _service().get_report_by_job(db, job_id=int(job_id))
    if report is None:
        raise AppError(
            code="voc.report_not_found",
            message="Report not found",
            http_status=404,
            details={"job_id": int(job_id)},
        )
    return ReviewAnalysisReport.model_validate(report.payload_json)


@router.get("/health", summary="VOC health")
async def voc_health():
    return {"status": "ok"}
