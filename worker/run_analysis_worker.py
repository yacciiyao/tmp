# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 启动分析任务Worker

from __future__ import annotations

import asyncio

from infrastructures.vconfig import vconfig
from worker.analysis_worker import AnalysisWorker


async def main() -> None:
    worker = AnalysisWorker()
    await worker.run_forever(poll_seconds=int(vconfig.worker_poll_interval))


if __name__ == "__main__":
    asyncio.run(main())
