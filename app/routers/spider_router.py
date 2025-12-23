# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 爬虫任务回调/状态更新接口（用于爬虫或人工模拟回填结果）

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from domains.error_domain import PermissionDeniedError
from infrastructures.db.orm.user_orm import UserORM
from services.jobs.analysis_job_service import AnalysisJobService
from services.spider.spider_task_service import SpiderTaskService

router = APIRouter(prefix="/spider", tags=["spider"])

_spider_svc = SpiderTaskService()
_job_svc = AnalysisJobService()


class SpiderTaskReadyReq(BaseModel):
    result_locator: Dict[str, Any] = Field(default_factory=dict, description="爬虫结果定位信息（如 crawl_batch_no ）")


class SpiderTaskFailedReq(BaseModel):
    error_code: str = Field(..., description="错误码")
    error_message: str = Field(..., description="错误信息")


class SpiderTaskStatusResp(BaseModel):
    task_id: int
    status: int
    result_locator: Dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


def _ensure_admin(user: UserORM) -> None:
    if user.role != "admin":
        raise PermissionDeniedError(message="仅管理员可操作", details={})


@router.post("/tasks/{task_id}/ready", response_model=SpiderTaskStatusResp)
async def mark_task_ready(
    task_id: int,
    req: SpiderTaskReadyReq,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
) -> SpiderTaskStatusResp:
    _ensure_admin(current_user)

    task = await _spider_svc.get_task(db, task_id=task_id)
    if not task:
        return SpiderTaskStatusResp(task_id=task_id, status=0)

    await _spider_svc.mark_ready(db, task_id=task_id, result_locator=req.result_locator)
    await _job_svc.mark_ready_by_spider_task_id(db, spider_task_id=task_id)

    task = await _spider_svc.get_task(db, task_id=task_id)
    return SpiderTaskStatusResp(
        task_id=int(task.task_id),
        status=int(task.status),
        result_locator=dict(task.result_locator) if task.result_locator else {},
        error_code=str(task.error_code) if task.error_code is not None else None,
        error_message=str(task.error_message) if task.error_message is not None else None,
    )


@router.post("/tasks/{task_id}/failed", response_model=SpiderTaskStatusResp)
async def mark_task_failed(
    task_id: int,
    req: SpiderTaskFailedReq,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
) -> SpiderTaskStatusResp:
    _ensure_admin(current_user)

    task = await _spider_svc.get_task(db, task_id=task_id)
    if not task:
        return SpiderTaskStatusResp(task_id=task_id, status=0)

    await _spider_svc.mark_failed(db, task_id=task_id, error_code=req.error_code, error_message=req.error_message)
    await _job_svc.mark_failed_by_spider_task_id(
        db,
        spider_task_id=task_id,
        error_code=req.error_code,
        error_message=req.error_message,
    )

    task = await _spider_svc.get_task(db, task_id=task_id)
    return SpiderTaskStatusResp(
        task_id=int(task.task_id),
        status=int(task.status),
        result_locator=dict(task.result_locator) if task.result_locator else {},
        error_code=str(task.error_code) if task.error_code is not None else None,
        error_message=str(task.error_message) if task.error_message is not None else None,
    )
