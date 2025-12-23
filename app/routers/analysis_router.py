# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 分析任务查询接口

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from domains.analysis_job_domain import AnalysisJobVO
from domains.error_domain import NotFoundError, PermissionDeniedError
from infrastructures.db.orm.analysis_job_orm import AnalysisJobORM
from infrastructures.db.orm.user_orm import UserORM
from services.jobs.analysis_job_service import AnalysisJobService

router = APIRouter(prefix="/analysis", tags=["analysis"])

_svc = AnalysisJobService()


class AnalysisJobDetailResp(BaseModel):
    job: AnalysisJobVO


class AnalysisJobListResp(BaseModel):
    items: list[AnalysisJobVO]
    limit: int
    offset: int


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


@router.get("/jobs/{job_id}", response_model=AnalysisJobDetailResp)
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
) -> AnalysisJobDetailResp:
    job = await _svc.get_job(db, job_id=job_id)
    if not job:
        raise NotFoundError(message="任务不存在", details={"job_id": job_id})

    is_admin = current_user.role == "admin"
    if (not is_admin) and job.created_by != current_user.user_id:
        raise PermissionDeniedError(message="无权限访问该任务", details={"job_id": job_id})

    return AnalysisJobDetailResp(job=_job_to_vo(job))


@router.get("/jobs", response_model=AnalysisJobListResp)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
    job_type: Optional[int] = Query(None, description="分析任务类型（int）"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AnalysisJobListResp:
    is_admin = current_user.role == "admin"
    created_by = None if is_admin else current_user.user_id

    rows = await _svc.list_jobs(
        db,
        created_by=created_by,
        job_type=job_type,
        limit=limit,
        offset=offset,
    )
    return AnalysisJobListResp(items=[_job_to_vo(x) for x in rows], limit=limit, offset=offset)
