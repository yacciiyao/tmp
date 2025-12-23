# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 爬虫任务服务（创建/查询/入队状态流转），不实现爬虫逻辑
from __future__ import annotations

import json
import asyncio
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from domains.spider_domain import SpiderTaskStatus
from infrastructures.db.orm.spider_orm import SpiderTaskORM
from infrastructures.db.repository.spider_repository import SpiderRepository
from infrastructures.spider.redis_gateway import RedisGateway
from infrastructures.vconfig import get_config


class SpiderTaskService:
    def __init__(self) -> None:
        self.repo = SpiderRepository()
        cfg = get_config()
        self.gateway = RedisGateway(
            redis_url=cfg.spider_redis_url,
            list_key=cfg.spider_redis_list_key,
            timeout_seconds=cfg.spider_redis_timeout_seconds,
        )

    async def create_task(
        self,
        db: AsyncSession,
        *,
        task_type: str,
        task_key: str,
        biz: str,
        payload: Dict[str, Any],
        result_tables: List[str],
        created_by: Optional[int] = None,
    ) -> SpiderTaskORM:
        return await self.repo.create(
            db,
            task_type=task_type,
            task_key=task_key,
            biz=biz,
            payload=payload,
            result_tables=result_tables,
            created_by=created_by,
        )

    async def enqueue_task(self, db: AsyncSession, task: SpiderTaskORM) -> None:
        if task.status != SpiderTaskStatus.CREATED.value:
            return

        msg = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "task_key": task.task_key,
            "biz": task.biz,
            "payload": task.payload,
            "result_tables": task.result_tables,
            "created_at": task.created_at,
        }
        await asyncio.to_thread(self.gateway.lpush_json, json.dumps(msg, ensure_ascii=False))
        await self.repo.mark_enqueued(db, task.task_id)

    async def get_task(self, db: AsyncSession, task_id: int) -> Optional[SpiderTaskORM]:
        return await self.repo.get_by_id(db, task_id)

    async def get_by_key(self, db: AsyncSession, task_key: str) -> Optional[SpiderTaskORM]:
        return await self.repo.get_by_key(db, task_key)

    async def mark_ready(self, db: AsyncSession, task_id: int, result_locator: Dict[str, Any]) -> None:
        await self.repo.mark_ready(db, task_id, result_locator)

    async def mark_failed(self, db: AsyncSession, task_id: int, error_code: str, error_message: str) -> None:
        await self.repo.mark_failed(db, task_id, error_code, error_message)
