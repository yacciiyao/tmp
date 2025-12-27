# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC worker (async background execution for queued voc jobs)

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.vlogger import vlogger
from infrastructures.db.repository.voc_repository import VocRepository
from infrastructures.db.spider_orm.spider_orm_base import SpiderAsyncSessionFactory
from services.voc.voc_job_service import VocJobService


@dataclass
class VocWorker:
    """Background worker that consumes queued VOC jobs.

    Contract:
        - API enqueues a job by setting status=EXTRACTING and stage='queued'
        - Worker claims and runs pipeline.
    """

    db_factory: Callable[[], AsyncSession]
    worker_id: str = "voc-worker-1"
    lease_seconds: int = 600
    idle_sleep: float = 2.0

    async def run_forever(self) -> None:
        while True:
            ran = await self._run_once()
            if not ran:
                await asyncio.sleep(self.idle_sleep)

    async def _run_once(self) -> bool:
        # 1) claim a job in a short transaction
        async with self.db_factory() as db:
            async with db.begin():
                job = await VocRepository.claim_next_job(
                    db,
                    worker_id=self.worker_id,
                    lease_seconds=self.lease_seconds,
                )
                if job is None:
                    return False

        job_id = int(job.job_id)
        vlogger.info("voc worker claimed job_id=%s", job_id)

        # 2) run pipeline (service DB + spider(results) DB)
        svc = VocJobService()
        try:
            async with self.db_factory() as db:
                async with SpiderAsyncSessionFactory() as spider_db:
                    try:
                        await svc.run_review_job_pipeline(db=db, spider_db=spider_db, job_id=job_id)
                    finally:
                        # Explicitly enforce read-only policy
                        await spider_db.rollback()
            vlogger.info("voc worker finished job_id=%s", job_id)
        except Exception as e:
            # pipeline is responsible for marking FAILED (and committing)
            vlogger.exception("voc worker error job_id=%s err=%s", job_id, e)

        return True
