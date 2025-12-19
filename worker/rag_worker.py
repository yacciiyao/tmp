# -*- coding: utf-8 -*-
# @File: rag_worker.py

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Any

from sqlalchemy.ext.asyncio import AsyncSession

from domains.rag_domain import JobResultStatus, JobStatus
from infrastructures.db.repository.rag_repository import RagRepository

log = logging.getLogger(__name__)


@dataclass
class RagWorker:
    repo: RagRepository
    db_factory: Callable[[], AsyncSession]
    pipeline: Any

    worker_id: str = "rag-worker"
    lease_seconds: int = 60
    idle_sleep: float = 3.0

    async def run_forever(self) -> None:
        while True:
            ran = await self._run_once()
            if not ran:
                await asyncio.sleep(self.idle_sleep)

    async def _run_once(self) -> bool:
        async with self.db_factory() as db:
            async with db.begin():
                job = await self.repo.claim_next_job(db, worker_id=self.worker_id, lease_seconds=self.lease_seconds)
                if job is None:
                    return False

        # pipeline 执行
        result = await self.pipeline.run_job(job_id=int(job.job_id), worker_id=self.worker_id)

        # retryable => 标记 FAILED（保留 try_count/max_retries 语义，让 claim_next_job 重新捞）
        if result.status == JobResultStatus.RETRYABLE:
            async with self.db_factory() as db:
                async with db.begin():
                    await self.repo.finish_job(
                        db,
                        job_id=int(job.job_id),
                        status=int(JobStatus.FAILED),
                        last_error=result.message or "retryable error",
                        clear_lock=True,
                    )

        # succeeded => cleanup older versions（best-effort）
        if result.status == JobResultStatus.SUCCEEDED:
            await self.pipeline.cleanup_after_commit(
                kb_space=str(job.kb_space),
                document_id=int(job.document_id),
                keep_index_version=int(job.index_version),
            )

        return True
