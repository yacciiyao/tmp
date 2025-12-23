# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import hashlib
from typing import Optional, List, Dict, Any, Sequence

from sqlalchemy import select, update, or_, and_, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domains.rag_domain import DocumentStatus, JobStatus
from infrastructures.db.orm.rag_orm import MetaRagSpacesORM, MetaRagDocumentsORM, OpsRagIngestJobsORM, StgRagChunksORM
from infrastructures.db.repository.repository_base import now_ts


class RagRepository:
    # -------- Space --------

    @staticmethod
    async def create_space(
            db: AsyncSession,
            *,
            kb_space: str,
            display_name: str,
            description: Optional[str] = None,
            enabled: int = 1,
            status: int = 1,
    ) -> MetaRagSpacesORM:
        space = MetaRagSpacesORM(
            kb_space=kb_space,
            display_name=display_name,
            description=description,
            enabled=int(enabled),
            status=int(status),
        )
        db.add(space)
        await db.flush()
        return space

    @staticmethod
    async def get_space(db: AsyncSession, *, kb_space: str) -> Optional[MetaRagSpacesORM]:
        stmt = select(MetaRagSpacesORM).where(MetaRagSpacesORM.kb_space == kb_space)
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def list_spaces(
            db: AsyncSession,
            *,
            enabled: Optional[int] = None,
            status: Optional[int] = None,
            limit: int = 50,
            offset: int = 0,
    ) -> List[MetaRagSpacesORM]:
        stmt = select(MetaRagSpacesORM)
        if enabled is not None:
            stmt = stmt.where(MetaRagSpacesORM.enabled == int(enabled))
        if status is not None:
            stmt = stmt.where(MetaRagSpacesORM.status == int(status))
        stmt = stmt.offset(int(offset)).limit(int(limit))

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_space(
            db: AsyncSession,
            *,
            kb_space: str,
            display_name: Optional[str] = None,
            description: Optional[str] = None,
            enabled: Optional[int] = None,
            status: Optional[int] = None,
    ) -> int:
        values = {}
        if display_name is not None:
            values["display_name"] = display_name
        if description is not None:
            values["description"] = description
        if enabled is not None:
            values["enabled"] = int(enabled)
        if status is not None:
            values["status"] = int(status)

        if not values:
            return 0

        values["updated_at"] = now_ts()

        stmt = update(MetaRagSpacesORM).where(MetaRagSpacesORM.kb_space == kb_space).values(**values)
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    async def delete_space(self, db: AsyncSession, *, kb_space: str) -> int:
        ts = now_ts()
        stmt = (
            update(MetaRagSpacesORM)
            .where(MetaRagSpacesORM.kb_space == kb_space)
            .values(enabled=0, status=0, updated_at=ts)
        )
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    @staticmethod
    async def create_document(
            db: AsyncSession,
            *,
            kb_space: str = "default",
            filename: str,
            content_type: str,
            size: int,
            storage_uri: str,
            sha256: str,
            uploader_user_id: int,
            status: int = DocumentStatus.UPLOADED,
    ) -> MetaRagDocumentsORM:
        doc = MetaRagDocumentsORM(
            kb_space=kb_space,
            filename=filename,
            content_type=content_type,
            size=int(size),
            storage_uri=storage_uri,
            sha256=sha256,
            status=int(status),
            uploader_user_id=int(uploader_user_id),
        )
        db.add(doc)
        await db.flush()
        return doc

    @staticmethod
    async def get_document(
            db: AsyncSession,
            *,
            document_id: int,
            include_deleted: bool = False,
    ) -> Optional[MetaRagDocumentsORM]:
        stmt = select(MetaRagDocumentsORM).where(MetaRagDocumentsORM.document_id == int(document_id))
        if not include_deleted:
            stmt = stmt.where(MetaRagDocumentsORM.status != DocumentStatus.DELETED)
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def list_documents(
            db: AsyncSession,
            *,
            kb_space: Optional[str] = None,
            document_id: Optional[int] = None,
            statuses: Optional[List[int]] = None,
            limit: int = 50,
            offset: int = 0,
    ) -> List[MetaRagDocumentsORM]:
        stmt = select(MetaRagDocumentsORM)

        if kb_space is not None:
            stmt = stmt.where(MetaRagDocumentsORM.kb_space == kb_space)
        if document_id is not None:
            stmt = stmt.where(MetaRagDocumentsORM.document_id == int(document_id))

        if statuses is None:
            stmt = stmt.where(MetaRagDocumentsORM.status != DocumentStatus.DELETED)
        else:
            stmt = stmt.where(MetaRagDocumentsORM.status.in_([int(x) for x in statuses]))

        stmt = stmt.offset(int(offset)).limit(int(limit))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_document_status(
            db: AsyncSession,
            *,
            document_id: int,
            status: int,
            last_error: Optional[str] = None,
    ) -> int:
        values = {"status": int(status), "updated_at": now_ts()}
        if last_error is not None:
            values["last_error"] = last_error

        stmt = (
            update(MetaRagDocumentsORM)
            .where(MetaRagDocumentsORM.document_id == int(document_id))
            .values(**values)
        )
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    @staticmethod
    async def set_active_index_version(
            db: AsyncSession,
            *,
            document_id: int,
            active_index_version: int,
    ) -> int:
        stmt = (
            update(MetaRagDocumentsORM)
            .where(MetaRagDocumentsORM.document_id == int(document_id))
            .values(active_index_version=int(active_index_version), updated_at=now_ts())
        )
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    @staticmethod
    async def update_document_filename(
            db: AsyncSession,
            *,
            document_id: int,
            filename: str,
    ) -> int:
        stmt = (
            update(MetaRagDocumentsORM)
            .where(MetaRagDocumentsORM.document_id == int(document_id))
            .values(filename=str(filename), updated_at=now_ts())
        )
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    @staticmethod
    async def mark_document_deleted(
            db: AsyncSession,
            *,
            document_id: int,
    ) -> int:
        ts = now_ts()
        stmt = (
            update(MetaRagDocumentsORM)
            .where(MetaRagDocumentsORM.document_id == int(document_id))
            .values(status=DocumentStatus.DELETED, deleted_at=ts, updated_at=ts)
        )
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    @staticmethod
    async def mark_documents_deleted_by_space(
            db: AsyncSession,
            *,
            kb_space: str,
    ) -> int:
        ts = now_ts()
        stmt = (
            update(MetaRagDocumentsORM)
            .where(MetaRagDocumentsORM.kb_space == kb_space)
            .values(status=DocumentStatus.DELETED, deleted_at=ts, updated_at=ts)
        )
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    async def delete_space_cascade(
            self,
            db: AsyncSession,
            *,
            kb_space: str,
    ) -> tuple[int, int]:
        space_rows = await self.delete_space(db, kb_space=kb_space)
        doc_rows = await self.mark_documents_deleted_by_space(db, kb_space=kb_space)
        await self.cancel_jobs_by_space(db, kb_space=kb_space, last_error="space deleted")
        return space_rows, doc_rows

    @staticmethod
    async def get_job(db: AsyncSession, *, job_id: int) -> Optional[OpsRagIngestJobsORM]:
        stmt = select(OpsRagIngestJobsORM).where(OpsRagIngestJobsORM.job_id == int(job_id))
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def get_job_by_idempotency_key(db: AsyncSession, *, idempotency_key: str) -> Optional[OpsRagIngestJobsORM]:
        stmt = select(OpsRagIngestJobsORM).where(OpsRagIngestJobsORM.idempotency_key == idempotency_key)
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def list_jobs(
            db: AsyncSession,
            *,
            kb_space: Optional[str] = None,
            document_id: Optional[int] = None,
            statuses: Optional[List[int]] = None,
            limit: int = 50,
            offset: int = 0,
    ) -> List[OpsRagIngestJobsORM]:
        stmt = select(OpsRagIngestJobsORM)

        if kb_space is not None:
            stmt = stmt.where(OpsRagIngestJobsORM.kb_space == kb_space)
        if document_id is not None:
            stmt = stmt.where(OpsRagIngestJobsORM.document_id == int(document_id))

        if statuses:
            stmt = stmt.where(OpsRagIngestJobsORM.status.in_([int(x) for x in statuses]))

        stmt = stmt.order_by(OpsRagIngestJobsORM.job_id.desc()).offset(int(offset)).limit(int(limit))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def allocate_index_version(db: AsyncSession, *, document_id: int) -> int:
        stmt = (
            select(MetaRagDocumentsORM.active_index_version)
            .where(MetaRagDocumentsORM.document_id == int(document_id))
            .with_for_update()
        )
        res = await db.execute(stmt)
        active_ver = res.scalar_one_or_none()
        if active_ver is None:
            return 1
        return int(active_ver) + 1

    def _make_idempotency_key(self, *, document_id: int, pipeline_version: str, index_version: int) -> str:
        raw = f"{int(document_id)}:{pipeline_version}:{int(index_version)}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    async def create_job_for_document(
            self,
            db: AsyncSession,
            *,
            document_id: int,
            kb_space: str,
            pipeline_version: str = "v1",
            max_retries: int = 3,
    ) -> OpsRagIngestJobsORM:
        index_version = await self.allocate_index_version(db, document_id=document_id)
        idem = self._make_idempotency_key(
            document_id=document_id, pipeline_version=pipeline_version, index_version=index_version
        )

        job = OpsRagIngestJobsORM(
            document_id=int(document_id),
            kb_space=kb_space,
            pipeline_version=pipeline_version,
            index_version=int(index_version),
            idempotency_key=idem,
            status=JobStatus.PENDING,
            try_count=0,
            max_retries=int(max_retries),
        )
        db.add(job)

        try:
            await db.flush()
            return job
        except IntegrityError:
            await db.rollback()
            existing = await self.get_job_by_idempotency_key(db, idempotency_key=idem)
            if existing is None:
                raise
            return existing

    @staticmethod
    async def claim_next_job(
            db: AsyncSession,
            *,
            worker_id: str,
            lease_seconds: int,
    ) -> Optional[OpsRagIngestJobsORM]:
        now = now_ts()
        lease_until = now + int(lease_seconds)

        claimable = or_(
            OpsRagIngestJobsORM.status == JobStatus.PENDING,
            and_(OpsRagIngestJobsORM.status == JobStatus.FAILED,
                 OpsRagIngestJobsORM.try_count < OpsRagIngestJobsORM.max_retries),
            and_(
                OpsRagIngestJobsORM.status == JobStatus.RUNNING,
                or_(OpsRagIngestJobsORM.locked_until.is_(None), OpsRagIngestJobsORM.locked_until < now),
                OpsRagIngestJobsORM.try_count < OpsRagIngestJobsORM.max_retries,
            ),
        )

        stmt = (
            select(OpsRagIngestJobsORM)
            .where(claimable)
            .order_by(OpsRagIngestJobsORM.job_id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        res = await db.execute(stmt)
        job = res.scalars().first()
        if job is None:
            return None

        job.status = JobStatus.RUNNING
        job.locked_by = worker_id
        job.locked_until = lease_until
        job.try_count = int(job.try_count or 0) + 1
        job.updated_at = now

        await db.flush()
        return job

    @staticmethod
    async def renew_job_lease(
            db: AsyncSession,
            *,
            job_id: int,
            worker_id: str,
            lease_seconds: int,
    ) -> int:
        now = now_ts()
        lease_until = now + int(lease_seconds)

        stmt = (
            update(OpsRagIngestJobsORM)
            .where(OpsRagIngestJobsORM.job_id == int(job_id))
            .where(OpsRagIngestJobsORM.status == JobStatus.RUNNING)
            .where(OpsRagIngestJobsORM.locked_by == worker_id)
            .values(locked_until=lease_until, updated_at=now)
        )
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    @staticmethod
    async def finish_job(
            db: AsyncSession,
            *,
            job_id: int,
            status: int,
            last_error: Optional[str] = None,
            clear_lock: bool = True,
    ) -> int:
        values = {"status": int(status), "updated_at": now_ts()}
        if last_error is not None:
            values["last_error"] = last_error
        if clear_lock:
            values["locked_by"] = None
            values["locked_until"] = None

        stmt = update(OpsRagIngestJobsORM).where(OpsRagIngestJobsORM.job_id == int(job_id)).values(**values)
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    async def cancel_jobs_by_document(
            self,
            db: AsyncSession,
            *,
            document_id: int,
            last_error: Optional[str] = None,
    ) -> int:
        values = {"status": JobStatus.CANCELLED, "updated_at": now_ts(), "locked_by": None, "locked_until": None}
        if last_error is not None:
            values["last_error"] = last_error

        stmt = (
            update(OpsRagIngestJobsORM)
            .where(OpsRagIngestJobsORM.document_id == int(document_id))
            .where(OpsRagIngestJobsORM.status.in_([JobStatus.PENDING, JobStatus.RUNNING, JobStatus.FAILED]))
            .values(**values)
        )
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    @staticmethod
    async def cancel_jobs_by_space(
            db: AsyncSession,
            *,
            kb_space: str,
            last_error: Optional[str] = None,
    ) -> int:
        values = {"status": JobStatus.CANCELLED, "updated_at": now_ts(), "locked_by": None, "locked_until": None}
        if last_error is not None:
            values["last_error"] = last_error

        stmt = (
            update(OpsRagIngestJobsORM)
            .where(OpsRagIngestJobsORM.kb_space == kb_space)
            .where(OpsRagIngestJobsORM.status.in_([JobStatus.PENDING, JobStatus.RUNNING, JobStatus.FAILED]))
            .values(**values)
        )
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    @staticmethod
    async def create_chunks(db: AsyncSession, *, chunks: List[Dict[str, Any]]) -> int:
        if not chunks:
            return 0

        objs = []
        for c in chunks:
            item = dict(c)
            item.pop("created_at", None)
            objs.append(StgRagChunksORM(**item))

        db.add_all(objs)
        await db.flush()
        return len(objs)

    @staticmethod
    async def delete_chunks_by_document_version(
            db: AsyncSession,
            *,
            document_id: int,
            index_version: int,
    ) -> int:
        stmt = (
            delete(StgRagChunksORM)
            .where(StgRagChunksORM.document_id == int(document_id))
            .where(StgRagChunksORM.index_version == int(index_version))
        )
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    async def replace_chunks_by_document_version(
            self,
            db: AsyncSession,
            *,
            document_id: int,
            index_version: int,
            chunks: List[Dict[str, Any]],
    ) -> int:
        await self.delete_chunks_by_document_version(db, document_id=document_id, index_version=index_version)
        return await self.create_chunks(db, chunks=chunks)

    @staticmethod
    async def list_chunks(
            db: AsyncSession,
            *,
            document_id: int,
            index_version: int,
            limit: int = 200,
            offset: int = 0,
    ) -> List[StgRagChunksORM]:
        stmt = (
            select(StgRagChunksORM)
            .where(StgRagChunksORM.document_id == int(document_id))
            .where(StgRagChunksORM.index_version == int(index_version))
            .order_by(StgRagChunksORM.chunk_index.asc())
            .offset(int(offset))
            .limit(int(limit))
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_chunks_by_ids(
            db: AsyncSession,
            *,
            chunk_ids: Sequence[str],
            kb_space: Optional[str] = None,
    ) -> List[StgRagChunksORM]:
        if not chunk_ids:
            return []

        stmt = select(StgRagChunksORM).where(StgRagChunksORM.chunk_id.in_(list(chunk_ids)))
        if kb_space:
            stmt = stmt.where(StgRagChunksORM.kb_space == kb_space)

        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)

    @staticmethod
    async def get_searchable_chunks_by_ids(
            db: AsyncSession,
            *,
            chunk_ids: Sequence[str],
            kb_space: str,
    ) -> List[StgRagChunksORM]:
        """
        Search 专用：只返回“可检索”的 chunk
        判定规则：
        - documents.status == INDEXED
        - documents.status != DELETED
        - documents.active_index_version 不为空
        - chunks.index_version == documents.active_index_version
        - kb_space 一致
        """
        if not chunk_ids:
            return []

        stmt = (
            select(StgRagChunksORM)
            .join(MetaRagDocumentsORM, MetaRagDocumentsORM.document_id == StgRagChunksORM.document_id)
            .where(StgRagChunksORM.chunk_id.in_(list(chunk_ids)))
            .where(StgRagChunksORM.kb_space == kb_space)
            .where(MetaRagDocumentsORM.kb_space == kb_space)
            .where(MetaRagDocumentsORM.status == int(DocumentStatus.INDEXED))
            .where(MetaRagDocumentsORM.status != int(DocumentStatus.DELETED))
            .where(MetaRagDocumentsORM.active_index_version.is_not(None))
            .where(StgRagChunksORM.index_version == MetaRagDocumentsORM.active_index_version)
        )

        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)
