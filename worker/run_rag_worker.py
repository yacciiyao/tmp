# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import asyncio

from infrastructures.db.orm.orm_base import AsyncSessionFactory, init_db
from infrastructures.db.repository.rag_repository import RagRepository
from infrastructures.embedding.dummy_embedder import DummyEmbedder
from infrastructures.index.es_index import ESIndex
from infrastructures.index.milvus_index import MilvusIndex
from infrastructures.parsing.chunker import Chunker
from infrastructures.parsing.local_parser import LocalParser
from infrastructures.vconfig import vconfig
from infrastructures.vlogger import vlogger
from services.rag.ingest_pipeline import IngestPipeline
from worker.rag_worker import RagWorker


async def _ensure_default_space(repo: RagRepository) -> None:
    async with AsyncSessionFactory() as db:
        async with db.begin():
            space = await repo.get_space(db, kb_space="default")
            if space is None:
                await repo.create_space(
                    db,
                    kb_space="default",
                    display_name="Default Space",
                    description="Auto created by worker",
                    enabled=1,
                    status=1,
                )


async def main() -> None:
    await init_db()
    vlogger.info("worker database schema ensured")

    repo = RagRepository()
    await _ensure_default_space(repo)
    vlogger.info("default space ensured")

    parser = LocalParser()

    chunker = Chunker(max_chars=800, overlap=80)

    embedder = DummyEmbedder(dim=int(vconfig.embedding_dim))
    vlogger.info("embedder=%s dim=%s", embedder.__class__.__name__, int(vconfig.embedding_dim))

    es_index = ESIndex()
    milvus_index = MilvusIndex()

    pipeline = IngestPipeline(
        repo=repo,
        db_factory=AsyncSessionFactory,
        parser=parser,
        chunker=chunker,
        embedder=embedder,
        es_index=es_index,
        milvus_index=milvus_index,
    )

    worker = RagWorker(
        repo=repo,
        db_factory=AsyncSessionFactory,
        pipeline=pipeline,
        worker_id="rag-worker-1",
        lease_seconds=60,
        idle_sleep=float(vconfig.worker_poll_interval),
    )

    vlogger.info("rag worker started worker_id=%s", worker.worker_id)
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
