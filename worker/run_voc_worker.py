# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Run VOC worker (v1: review analysis)

from __future__ import annotations

import asyncio

from infrastructures.db.orm.orm_base import AsyncSessionFactory, init_db, close_db_engine
from infrastructures.db.repository.spider_results_repository import SpiderResultsRepository
from infrastructures.db.repository.voc_repository import VocRepository
from infrastructures.vconfig import vconfig
from infrastructures.vlogger import vlogger
from services.voc.pipelines.review_analysis import ReviewAnalysisPipeline
from worker.voc_worker import VocWorker
from infrastructures.db.spider_orm.spider_orm_base import close_spider_engine


async def main() -> None:
    await init_db()
    vlogger.info("worker database schema ensured")

    repo = VocRepository()
    spider_repo = SpiderResultsRepository()

    pipeline = ReviewAnalysisPipeline(
        repo=repo,
        db_factory=AsyncSessionFactory,
        spider_repo=spider_repo,
    )

    worker = VocWorker(
        repo=repo,
        db_factory=AsyncSessionFactory,
        pipeline=pipeline,
        worker_id="voc-worker-1",
        lease_seconds=120,
        idle_sleep=float(vconfig.worker_poll_interval),
    )

    vlogger.info("voc worker started worker_id=%s", worker.worker_id)
    try:
        await worker.run_forever()
    finally:
        # Ensure DB pools are disposed cleanly (important on Windows)
        try:
            await close_spider_engine()
        except Exception:
            pass
        try:
            await close_db_engine()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
