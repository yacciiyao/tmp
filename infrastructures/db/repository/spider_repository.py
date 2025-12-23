# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 爬虫任务仓储（spider_tasks）
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domains.spider_domain import SpiderTaskStatus
from infrastructures.db.orm.spider_orm import SpiderTaskORM


class SpiderRepository:
    async def create(
        self,
        db: AsyncSession,
        task_type: str,
        task_key: str,
        biz: str,
        payload: Dict[str, Any],
        result_tables: List[str],
        created_by: Optional[int] = None,
    ) -> SpiderTaskORM:
        task = SpiderTaskORM(
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

    async def mark_ready(self, db: AsyncSession, task_id: int, result_locator: Dict[str, Any]) -> None:
        stmt = (
            update(SpiderTaskORM)
            .where(SpiderTaskORM.task_id == task_id)
            .values(
                status=SpiderTaskStatus.READY.value,
                result_locator=result_locator,
                error_code=None,
                error_message=None,
            )
        )
        await db.execute(stmt)

    async def mark_failed(self, db: AsyncSession, task_id: int, error_code: str, error_message: str) -> None:
        stmt = (
            update(SpiderTaskORM)
            .where(SpiderTaskORM.task_id == task_id)
            .values(status=SpiderTaskStatus.FAILED.value, error_code=error_code, error_message=error_message)
        )
        await db.execute(stmt)

    async def get_by_id(self, db: AsyncSession, task_id: int) -> Optional[SpiderTaskORM]:
        stmt = select(SpiderTaskORM).where(SpiderTaskORM.task_id == task_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_key(self, db: AsyncSession, task_key: str) -> Optional[SpiderTaskORM]:
        stmt = select(SpiderTaskORM).where(SpiderTaskORM.task_key == task_key)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def mark_enqueued(self, db: AsyncSession, task_id: int) -> None:
        stmt = update(SpiderTaskORM).where(SpiderTaskORM.task_id == task_id).values(status=20)
        await db.execute(stmt)

        await db.execute(stmt)
