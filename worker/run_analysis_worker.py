# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 启动分析任务Worker

from __future__ import annotations

import asyncio

from infrastructures.vconfig import VConfig
from infrastructures.vlogger import init_logging
from worker.analysis_worker import AnalysisWorker


async def main() -> None:
    cfg = VConfig()
    init_logging(cfg.log_level)

    worker = AnalysisWorker()
    await worker.run_forever(poll_seconds=int(cfg.worker_poll_interval))


if __name__ == "__main__":
    asyncio.run(main())
