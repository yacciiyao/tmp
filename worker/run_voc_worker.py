# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Run VOC worker.

from __future__ import annotations

import asyncio

from infrastructures.db.orm.orm_base import AsyncSessionFactory, init_db
from infrastructures.db.repository.voc_repository import VocRepository
from infrastructures.vconfig import vconfig
from infrastructures.vlogger import vlogger
from services.voc.voc_pipeline import VocPipeline
from worker.voc_worker import VocWorker


async def main() -> None:
    await init_db()
    vlogger.info("worker database schema ensured")

    repo = VocRepository()
    pipeline = VocPipeline(repo=repo)

    worker = VocWorker(
        repo=repo,
        db_factory=AsyncSessionFactory,
        pipeline=pipeline,
        worker_id="voc-worker-1",
        lease_seconds=60,
        idle_sleep=float(vconfig.worker_poll_interval),
    )

    vlogger.info("voc worker started worker_id=%s", worker.worker_id)
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
