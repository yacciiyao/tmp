# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from domains.rag_domain import DocumentStatus, JobResultStatus, JobRunResult, JobStage, JobStatus
from infrastructures.db.repository.rag_repository import RagRepository
from infrastructures.parsing.parser_base import ParseError
from infrastructures.vconfig import vconfig
from infrastructures.vlogger import vlogger


@dataclass
class IngestPipeline:
    repo: RagRepository
    db_factory: Callable[[], AsyncSession]

    parser: Any
    chunker: Any
    embedder: Any
    es_index: Any
    milvus_index: Any

    async def run_job(self, *, job_id: int, worker_id: str) -> JobRunResult:
        async with self.db_factory() as db:
            job = await self.repo.get_job(db, job_id=int(job_id))
            if job is None:
                return JobRunResult(
                    job_id=int(job_id),
                    document_id=0,
                    kb_space="",
                    status=JobResultStatus.SUCCEEDED,
                    message=f"job not found: {job_id}",
                    data={"stage": "load"},
                )

            if int(job.status) not in (int(JobStatus.PENDING), int(JobStatus.FAILED), int(JobStatus.RUNNING)):
                return JobRunResult(
                    job_id=int(job.job_id),
                    document_id=int(job.document_id),
                    kb_space=str(job.kb_space),
                    status=JobResultStatus.SUCCEEDED,
                    message="job not runnable",
                    data={"stage": "skip"},
                )

            if int(job.status) == int(JobStatus.RUNNING):
                locked_by = str(job.locked_by or "")
                if locked_by and locked_by != str(worker_id):
                    return JobRunResult(
                        job_id=int(job.job_id),
                        document_id=int(job.document_id),
                        kb_space=str(job.kb_space),
                        status=JobResultStatus.SUCCEEDED,
                        message="job locked by other worker",
                        data={"stage": "skip"},
                    )

            try:
                doc = await self.repo.get_document(db, document_id=int(job.document_id), include_deleted=True)
                if doc is None:
                    await self.repo.finish_job(
                        db,
                        job_id=int(job.job_id),
                        status=int(JobStatus.FAILED),
                        last_error="document not found",
                        clear_lock=True,
                    )
                    await db.commit()
                    return JobRunResult(
                        job_id=int(job.job_id),
                        document_id=int(job.document_id),
                        kb_space=str(job.kb_space),
                        status=JobResultStatus.RETRYABLE,
                        message="document not found",
                        data={"stage": JobStage.parse},
                    )

                if int(doc.status) == int(DocumentStatus.DELETED):
                    await self.repo.finish_job(
                        db,
                        job_id=int(job.job_id),
                        status=int(JobStatus.CANCELLED),
                        last_error="document deleted",
                        clear_lock=True,
                    )
                    await db.commit()
                    return JobRunResult(
                        job_id=int(job.job_id),
                        document_id=int(job.document_id),
                        kb_space=str(job.kb_space),
                        status=JobResultStatus.SUCCEEDED,
                        message="document deleted; job cancelled",
                        data={"stage": JobStage.parse},
                    )

                await self.repo.update_document_status(
                    db,
                    document_id=int(doc.document_id),
                    status=int(DocumentStatus.PROCESSING),
                )
                await db.commit()

                parsed = await self.parser.parse(
                    storage_uri=str(doc.storage_uri),
                    content_type=str(doc.content_type),
                )

                chunks: List[Dict[str, Any]] = await self.chunker.chunk(
                    parsed=parsed,
                    document_id=int(doc.document_id),
                    kb_space=str(job.kb_space),
                    index_version=int(job.index_version),
                )
                if not chunks:
                    raise ValueError("chunker returned empty chunks")

                await self.repo.replace_chunks_by_document_version(
                    db,
                    document_id=int(doc.document_id),
                    index_version=int(job.index_version),
                    chunks=chunks,
                )
                await db.commit()

                if bool(vconfig.milvus_enabled):
                    texts = [str(c.get("content") or "") for c in chunks]
                    vectors = await self.embedder.embed_documents(texts)
                    await self.milvus_index.upsert(chunks=chunks, vectors=vectors)

                # optional: es
                if bool(vconfig.es_enabled):
                    await self.es_index.upsert(chunks=chunks)

                # commit
                await self.repo.set_active_index_version(
                    db,
                    document_id=int(doc.document_id),
                    active_index_version=int(job.index_version),
                )
                await self.repo.update_document_status(
                    db,
                    document_id=int(doc.document_id),
                    status=int(DocumentStatus.INDEXED),
                )
                await self.repo.finish_job(
                    db,
                    job_id=int(job.job_id),
                    status=int(JobStatus.SUCCEEDED),
                    last_error=None,
                    clear_lock=True,
                )
                await db.commit()

                return JobRunResult(
                    job_id=int(job.job_id),
                    document_id=int(job.document_id),
                    kb_space=str(job.kb_space),
                    status=JobResultStatus.SUCCEEDED,
                    message="ok",
                    data={"stage": JobStage.commit, "worker_id": worker_id},
                )

            except ParseError as e:
                await self.repo.update_document_status(
                    db,
                    document_id=int(job.document_id),
                    status=int(DocumentStatus.FAILED),
                    last_error=str(e),
                )

                if bool(e.retryable):
                    await self.repo.finish_job(
                        db,
                        job_id=int(job.job_id),
                        status=int(JobStatus.FAILED),
                        last_error=str(e),
                        clear_lock=True,
                    )
                    await db.commit()
                    return JobRunResult(
                        job_id=int(job.job_id),
                        document_id=int(job.document_id),
                        kb_space=str(job.kb_space),
                        status=JobResultStatus.RETRYABLE,
                        message=str(e),
                        data={"stage": "error", "retryable": True},
                    )

                await self.repo.finish_job(
                    db,
                    job_id=int(job.job_id),
                    status=int(JobStatus.CANCELLED),
                    last_error=str(e),
                    clear_lock=True,
                )
                await db.commit()
                return JobRunResult(
                    job_id=int(job.job_id),
                    document_id=int(job.document_id),
                    kb_space=str(job.kb_space),
                    status=JobResultStatus.SUCCEEDED,
                    message=str(e),
                    data={"stage": "error", "retryable": False},
                )

            except Exception as e:
                await self.repo.update_document_status(
                    db,
                    document_id=int(job.document_id),
                    status=int(DocumentStatus.FAILED),
                    last_error=str(e),
                )
                await self.repo.finish_job(
                    db,
                    job_id=int(job.job_id),
                    status=int(JobStatus.FAILED),
                    last_error=str(e),
                    clear_lock=True,
                )
                await db.commit()

                return JobRunResult(
                    job_id=int(job.job_id),
                    document_id=int(job.document_id),
                    kb_space=str(job.kb_space),
                    status=JobResultStatus.RETRYABLE,
                    message=str(e),
                    data={"stage": "error"},
                )

    async def cleanup_after_commit(self, *, kb_space: str, document_id: int, keep_index_version: int) -> None:
        if bool(vconfig.es_enabled) and str(getattr(vconfig, "es_url", "") or "").strip():
            try:
                await self.es_index.delete_by_document(
                    kb_space=str(kb_space),
                    document_id=int(document_id),
                    keep_index_version=int(keep_index_version),
                )
            except Exception as e:
                vlogger.warning(
                    "cleanup es failed",
                    extra={
                        "kb_space": str(kb_space),
                        "document_id": int(document_id),
                        "keep_index_version": int(keep_index_version),
                        "err": str(e),
                    },
                )

        # Milvus cleanup
        if bool(vconfig.milvus_enabled) and str(getattr(vconfig, "milvus_uri", "") or "").strip():
            try:
                await self.milvus_index.delete_by_document(
                    kb_space=str(kb_space),
                    document_id=int(document_id),
                    keep_index_version=int(keep_index_version),
                )
            except Exception as e:
                vlogger.warning(
                    "cleanup milvus failed",
                    extra={
                        "kb_space": str(kb_space),
                        "document_id": int(document_id),
                        "keep_index_version": int(keep_index_version),
                        "err": str(e),
                    },
                )
