# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: entrypoint for running voc worker process

from __future__ import annotations

import asyncio

from infrastructures.db.orm.orm_base import AsyncSessionFactory, init_db
from infrastructures.vconfig import vconfig
from infrastructures.vlogger import vlogger
from worker.voc_worker import VocWorker


async def main() -> None:
    await init_db()
    vlogger.info("worker database schema ensured")

    worker = VocWorker(
        db_factory=AsyncSessionFactory,
        worker_id="voc-worker-1",
        lease_seconds=600,
        idle_sleep=float(vconfig.worker_poll_interval),
    )

    vlogger.info("voc worker started worker_id=%s", worker.worker_id)
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
