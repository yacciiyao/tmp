# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC worker (claims ready jobs and generates reports)

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Any

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.repository.voc_repository import VocRepository


@dataclass
class VocWorker:
    repo: VocRepository
    db_factory: Callable[[], AsyncSession]
    pipeline: Any

    worker_id: str = "voc-worker"
    lease_seconds: int = 120
    idle_sleep: float = 3.0

    async def run_forever(self) -> None:
        while True:
            ran = await self._run_once()
            if not ran:
                await asyncio.sleep(self.idle_sleep)

    async def _run_once(self) -> bool:
        # Claim a job (must be READY with run_id bound, enforced by repo.claim_next_job)
        async with self.db_factory() as db:
            async with db.begin():
                job = await self.repo.claim_next_job(db, worker_id=self.worker_id, lease_seconds=self.lease_seconds)
                if job is None:
                    return False

        # Execute pipeline outside transaction
        await self.pipeline.run_job(job_id=int(job.job_id), worker_id=self.worker_id)
        return True
