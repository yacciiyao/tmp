# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC router

from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domains.voc_domain import VocJobStatus
from infrastructures.db.orm.orm_deps import get_db
from infrastructures.db.spider_orm.spider_orm_deps import get_spider_db
from services.voc.voc_job_service import VocJobService


router = APIRouter(prefix="/voc", tags=["voc"])


class CreateReviewJobReq(BaseModel):
    site_code: str = Field(..., description="Marketplace/site code, e.g. US")
    asins: List[str] = Field(..., min_length=1)
    review_days: int = Field(365, ge=1, le=3650)
    run_now: bool = Field(False, description="If true, run pipeline synchronously; otherwise enqueue for worker")


class CreateVocJobReq(BaseModel):
    site_code: str = Field(..., description="Marketplace/site code, e.g. US")
    asins: List[str] = Field(default_factory=list, description="Target ASINs")
    competitor_asins: List[str] = Field(default_factory=list, description="Competitor ASINs")
    keywords: List[str] = Field(default_factory=list, description="Keywords for SERP analysis")
    review_days: int = Field(365, ge=1, le=3650)
    max_serp_page_num: Optional[int] = Field(2, ge=1, le=20, description="Max SERP page number to include")
    run_now: bool = Field(False, description="If true, run pipeline synchronously; otherwise enqueue for worker")


class JobResp(BaseModel):
    job_id: int
    status: int


@router.get("/ping")
async def ping():
    return {"status": "ok"}


@router.post("/reviews/jobs", response_model=JobResp)
async def create_review_job(
    req: CreateReviewJobReq,
    db: Annotated[AsyncSession, Depends(get_db)],
    spider_db: Annotated[AsyncSession, Depends(get_spider_db)],
):
    """Create a VOC review job.

    Behavior:
    - does NOT trigger spider crawling
    - reads existing daily spider(results) data
    - default: enqueue and let voc-worker run pipeline asynchronously
    - if run_now=true: runs pipeline in-request (dev/testing)
    """

    svc = VocJobService()
    job = await svc.create_or_reuse_review_job(db, site_code=req.site_code, asins=req.asins, review_days=req.review_days)

    if req.run_now and job.status not in (int(VocJobStatus.DONE), int(VocJobStatus.FAILED)):
        await svc.run_review_job_pipeline(db=db, spider_db=spider_db, job_id=job.job_id)
        job = await svc.get_job(db, job_id=job.job_id)  # reload
        assert job is not None
    elif not req.run_now and job.status not in (int(VocJobStatus.DONE), int(VocJobStatus.FAILED)):
        await svc.enqueue_review_job(db, job_id=int(job.job_id))
        job = await svc.get_job(db, job_id=job.job_id)  # reload
        assert job is not None

    return JobResp(job_id=int(job.job_id), status=int(job.status))


@router.post("/jobs", response_model=JobResp)
async def create_voc_job(
    req: CreateVocJobReq,
    db: Annotated[AsyncSession, Depends(get_db)],
    spider_db: Annotated[AsyncSession, Depends(get_spider_db)],
):
    """Create a VOC bundle job.

    Scope:
    - reviews for target asins
    - market.product_details for (target + competitor) asins
    - keyword.keyword_details for keywords
    - report.v1 aggregation

    Default: enqueue and let worker run asynchronously.
    """

    svc = VocJobService()
    job = await svc.create_or_reuse_voc_job(
        db,
        site_code=req.site_code,
        asins=req.asins,
        competitor_asins=req.competitor_asins,
        keywords=req.keywords,
        review_days=req.review_days,
        max_serp_page_num=req.max_serp_page_num,
    )

    if req.run_now and job.status not in (int(VocJobStatus.DONE), int(VocJobStatus.FAILED)):
        await svc.run_job_pipeline(db=db, spider_db=spider_db, job_id=int(job.job_id))
        job = await svc.get_job(db, job_id=int(job.job_id))
        assert job is not None
    elif not req.run_now and job.status not in (int(VocJobStatus.DONE), int(VocJobStatus.FAILED)):
        await svc.enqueue_job(db, job_id=int(job.job_id))
        job = await svc.get_job(db, job_id=int(job.job_id))
        assert job is not None

    return JobResp(job_id=int(job.job_id), status=int(job.status))


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = VocJobService()
    job = await svc.get_job(db, job_id=int(job_id))
    if job is None:
        return {"error": {"code": "voc.job_not_found", "message": f"job_id={job_id} not found"}}
    return {
        "job_id": int(job.job_id),
        "status": int(job.status),
        "stage": job.stage,
        "site_code": job.site_code,
        "scope_type": job.scope_type,
        "scope_value": job.scope_value,
        "params": job.params_json,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "failed_stage": job.failed_stage,
        "created_at": int(job.created_at),
        "updated_at": int(job.updated_at),
    }


@router.get("/jobs/{job_id}/outputs")
async def list_outputs(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = VocJobService()
    outs = await svc.list_outputs(db, job_id=int(job_id))
    return {
        "job_id": int(job_id),
        "items": [
            {
                "module_code": o.module_code,
                "schema_version": int(o.schema_version),
                "updated_at": int(o.updated_at),
            }
            for o in outs
        ],
    }


@router.get("/jobs/{job_id}/outputs/{module_code}")
async def get_output(
    job_id: int,
    module_code: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    svc = VocJobService()
    out = await svc.get_output(db, job_id=int(job_id), module_code=module_code)
    if out is None:
        return {"error": {"code": "voc.output_not_found", "message": f"output not found: {module_code}"}}
    return {
        "job_id": int(job_id),
        "module_code": out.module_code,
        "schema_version": int(out.schema_version),
        "payload": out.payload_json,
        "updated_at": int(out.updated_at),
    }


@router.get("/jobs/{job_id}/evidence")
async def list_evidence(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    module_code: Optional[str] = None,
):
    svc = VocJobService()
    items = await svc.list_evidence(db, job_id=int(job_id), module_code=module_code)
    return {
        "job_id": int(job_id),
        "module_code": module_code,
        "items": [i.model_dump() for i in items],
    }
