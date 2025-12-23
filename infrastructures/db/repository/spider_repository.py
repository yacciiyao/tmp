# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 爬虫任务仓储

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domains.spider_domain import SpiderTaskStatus
from infrastructures.db.orm.spider_orm import OpsSpiderTasksORM


class SpiderRepository:
    @staticmethod
    async def create(
            db: AsyncSession,
            task_type: str,
            task_key: str,
            biz: str,
            payload: Dict[str, Any],
            result_tables: List[str],
            created_by: Optional[int] = None,
    ) -> OpsSpiderTasksORM:
        task = OpsSpiderTasksORM(
            task_type=task_type,
            task_key=task_key,
            biz=biz,
            status=SpiderTaskStatus.CREATED.value,
            payload=payload,
            result_tables=result_tables,
            created_by=created_by,
        )
        db.add(task)
        await db.flush()
        return task

    @staticmethod
    async def mark_ready(db: AsyncSession, task_id: int, result_locator: Dict[str, Any]) -> None:
        stmt = (
            update(OpsSpiderTasksORM)
            .where(OpsSpiderTasksORM.task_id == task_id)
            .values(
                status=SpiderTaskStatus.READY.value,
                result_locator=result_locator,
                error_code=None,
                error_message=None,
            )
        )
        await db.execute(stmt)

    @staticmethod
    async def mark_failed(db: AsyncSession, task_id: int, error_code: str, error_message: str) -> None:
        stmt = (
            update(OpsSpiderTasksORM)
            .where(OpsSpiderTasksORM.task_id == task_id)
            .values(status=SpiderTaskStatus.FAILED.value, error_code=error_code, error_message=error_message)
        )
        await db.execute(stmt)

    @staticmethod
    async def get_by_id(db: AsyncSession, task_id: int) -> Optional[OpsSpiderTasksORM]:
        stmt = select(OpsSpiderTasksORM).where(OpsSpiderTasksORM.task_id == task_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_by_key(db: AsyncSession, task_key: str) -> Optional[OpsSpiderTasksORM]:
        stmt = select(OpsSpiderTasksORM).where(OpsSpiderTasksORM.task_key == task_key)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def mark_enqueued(db: AsyncSession, task_id: int) -> None:
        stmt = update(OpsSpiderTasksORM).where(OpsSpiderTasksORM.task_id == task_id).values(status=20)
        await db.execute(stmt)

        await db.execute(stmt)
