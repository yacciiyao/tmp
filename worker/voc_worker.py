# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC worker loop.

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from domains.voc_job_domain import VocJobStatus
from infrastructures.db.repository.voc_repository import VocRepository


@dataclass
class VocWorker:
    repo: VocRepository
    db_factory: Callable[[], AsyncSession]
    pipeline: Any

    worker_id: str = "voc-worker"
    lease_seconds: int = 60
    idle_sleep: float = 3.0
    eligible_statuses: Sequence[int] = (int(VocJobStatus.EXTRACTING),)

    async def run_forever(self) -> None:
        while True:
            ran = await self._run_once()
            if not ran:
                await asyncio.sleep(self.idle_sleep)

    async def _run_once(self) -> bool:
        # claim
        async with self.db_factory() as db:
            async with db.begin():
                job = await self.repo.claim_next_job(
                    db,
                    worker_id=self.worker_id,
                    lease_seconds=int(self.lease_seconds),
                    eligible_statuses=self.eligible_statuses,
                )
                if job is None:
                    return False

        # run pipeline
        async with self.db_factory() as db:
            async with db.begin():
                await self.pipeline.run_job(db, job_id=int(job.job_id), worker_id=self.worker_id)

        return True
