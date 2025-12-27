# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC repository (service DB).

from __future__ import annotations

from typing import Any, Dict, Optional, List

from sqlalchemy import select, update
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.orm.voc_orm import MetaVocJobsORM, StgVocOutputsORM, StgVocEvidenceORM
from infrastructures.db.repository.repository_base import now_ts


class VocRepository:
    # -----------------------------
    # Jobs
    # -----------------------------

    @staticmethod
    async def claim_next_job(
        db: AsyncSession,
        *,
        worker_id: str = "voc-worker",
        lease_seconds: int = 600,
    ) -> Optional[MetaVocJobsORM]:
        """Claim next queued (or stale) VOC job.

        This implementation avoids schema changes by relying on row-level locking.

        Queue contract (v1):
            - API enqueues a job by setting status=EXTRACTING and stage='queued'.
            - Worker claims with SELECT ... FOR UPDATE (SKIP LOCKED if supported).

        Stale reclaim (best-effort):
            - If a job is stuck in EXTRACTING/ANALYZING/PERSISTING and hasn't updated
              for lease_seconds, it can be reclaimed.
        """

        now = now_ts()
        stale_before = now - int(lease_seconds)

        # Candidate statuses: queued or potentially stuck.
        candidate_statuses = (30, 40, 50)  # EXTRACTING/ANALYZING/PERSISTING

        base_cond = and_(
            MetaVocJobsORM.status.in_(candidate_statuses),
            or_(
                MetaVocJobsORM.stage == "queued",
                MetaVocJobsORM.updated_at <= stale_before,
            ),
        )

        # Try SKIP LOCKED first (MySQL 8+/Postgres). Fallback to FOR UPDATE.
        stmt = (
            select(MetaVocJobsORM)
            .where(base_cond)
            .order_by(MetaVocJobsORM.created_at.asc())
            .limit(1)
        )
        try:
            stmt = stmt.with_for_update(skip_locked=True)
            res = await db.execute(stmt)
        except Exception:
            res = await db.execute(stmt.with_for_update())

        job = res.scalars().first()
        if job is None:
            return None

        # Mark as claimed (still EXTRACTING stage=extracting). Pipeline will move stages.
        await VocRepository.update_job_status(
            db,
            job_id=int(job.job_id),
            status=30,
            stage="extracting",
        )

        return job

    @staticmethod
    async def create_job(
        db: AsyncSession,
        *,
        input_hash: str,
        site_code: str,
        scope_type: str,
        scope_value: str,
        params_json: Dict[str, Any],
        status: int = 10,
        stage: Optional[str] = None,
        preferred_task_id: Optional[int] = None,
        preferred_run_id: Optional[int] = None,
    ) -> MetaVocJobsORM:
        job = MetaVocJobsORM(
            input_hash=str(input_hash),
            site_code=str(site_code),
            scope_type=str(scope_type),
            scope_value=str(scope_value),
            params_json=dict(params_json or {}),
            status=int(status),
            stage=stage,
            preferred_task_id=int(preferred_task_id) if preferred_task_id is not None else None,
            preferred_run_id=int(preferred_run_id) if preferred_run_id is not None else None,
        )
        db.add(job)
        await db.flush()
        return job

    @staticmethod
    async def get_job(db: AsyncSession, *, job_id: int) -> Optional[MetaVocJobsORM]:
        stmt = select(MetaVocJobsORM).where(MetaVocJobsORM.job_id == int(job_id))
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def get_job_by_hash(db: AsyncSession, *, input_hash: str) -> Optional[MetaVocJobsORM]:
        stmt = select(MetaVocJobsORM).where(MetaVocJobsORM.input_hash == str(input_hash))
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def update_job_status(
        db: AsyncSession,
        *,
        job_id: int,
        status: int,
        stage: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        failed_stage: Optional[str] = None,
    ) -> int:
        values: Dict[str, Any] = {"status": int(status), "updated_at": now_ts()}
        if stage is not None:
            values["stage"] = stage
        if error_code is not None:
            values["error_code"] = error_code
        if error_message is not None:
            values["error_message"] = error_message
        if failed_stage is not None:
            values["failed_stage"] = failed_stage

        stmt = update(MetaVocJobsORM).where(MetaVocJobsORM.job_id == int(job_id)).values(**values)
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    # -----------------------------
    # Outputs
    # -----------------------------

    @staticmethod
    async def upsert_output(
        db: AsyncSession,
        *,
        job_id: int,
        module_code: str,
        payload_json: Dict[str, Any],
        schema_version: int = 1,
    ) -> StgVocOutputsORM:
        # Fast path: try update first
        stmt = (
            update(StgVocOutputsORM)
            .where(StgVocOutputsORM.job_id == int(job_id), StgVocOutputsORM.module_code == str(module_code))
            .values(payload_json=dict(payload_json or {}), schema_version=int(schema_version), updated_at=now_ts())
        )
        res = await db.execute(stmt)
        if int(res.rowcount or 0) > 0:
            # reload
            got = await VocRepository.get_output(db, job_id=int(job_id), module_code=str(module_code))
            assert got is not None
            return got

        # Insert
        out = StgVocOutputsORM(
            job_id=int(job_id),
            module_code=str(module_code),
            payload_json=dict(payload_json or {}),
            schema_version=int(schema_version),
        )
        db.add(out)
        try:
            await db.flush()
            return out
        except IntegrityError:
            # concurrent insert -> retry as update
            await db.rollback()
            got = await VocRepository.get_output(db, job_id=int(job_id), module_code=str(module_code))
            if got is not None:
                return got
            raise

    @staticmethod
    async def get_output(db: AsyncSession, *, job_id: int, module_code: str) -> Optional[StgVocOutputsORM]:
        stmt = select(StgVocOutputsORM).where(
            StgVocOutputsORM.job_id == int(job_id),
            StgVocOutputsORM.module_code == str(module_code),
        )
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def list_outputs(db: AsyncSession, *, job_id: int, limit: int = 200, offset: int = 0) -> List[StgVocOutputsORM]:
        stmt = (
            select(StgVocOutputsORM)
            .where(StgVocOutputsORM.job_id == int(job_id))
            .order_by(StgVocOutputsORM.module_code.asc())
            .offset(int(offset))
            .limit(int(limit))
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # -----------------------------
    # Evidence
    # -----------------------------

    @staticmethod
    async def clear_evidence(db: AsyncSession, *, job_id: int, module_code: str) -> int:
        """Delete evidence for a job+module.

        v1 behavior: evidence is append-only per run. If rerunning a module, clear first.
        """

        from sqlalchemy import delete

        stmt = delete(StgVocEvidenceORM).where(
            StgVocEvidenceORM.job_id == int(job_id),
            StgVocEvidenceORM.module_code == str(module_code),
        )
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    @staticmethod
    async def insert_evidence_many(
        db: AsyncSession,
        *,
        job_id: int,
        module_code: str,
        items: List[Dict[str, Any]],
        chunk_size: int = 200,
    ) -> int:
        if not items:
            return 0

        total = 0
        for i in range(0, len(items), chunk_size):
            chunk = items[i : i + chunk_size]
            objs = []
            for it in chunk:
                objs.append(
                    StgVocEvidenceORM(
                        job_id=int(job_id),
                        module_code=str(module_code),
                        source_type=str(it["source_type"]),
                        source_id=int(it["source_id"]),
                        kind=str(it.get("kind")) if it.get("kind") is not None else None,
                        snippet=str(it.get("snippet") or ""),
                        meta_json=dict(it.get("meta_json") or {}),
                    )
                )
            db.add_all(objs)
            await db.flush()
            total += len(objs)
        return total

    @staticmethod
    async def list_evidence(
        db: AsyncSession,
        *,
        job_id: int,
        module_code: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> List[StgVocEvidenceORM]:
        stmt = select(StgVocEvidenceORM).where(StgVocEvidenceORM.job_id == int(job_id))
        if module_code is not None:
            stmt = stmt.where(StgVocEvidenceORM.module_code == str(module_code))
        stmt = stmt.order_by(StgVocEvidenceORM.evidence_id.asc()).offset(int(offset)).limit(int(limit))
        res = await db.execute(stmt)
        return list(res.scalars().all())
