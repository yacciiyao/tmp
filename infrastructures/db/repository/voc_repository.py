# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC repository (jobs / spider_tasks / reports). CRUD only.

from __future__ import annotations

from typing import Optional, List, Any

from sqlalchemy import select, update, or_, and_, exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domains.rag_domain import JobStatus
from infrastructures.db.orm.voc_orm import OpsVocJobsORM, OpsVocJobSpiderTasksORM, OpsVocReportsORM
from infrastructures.db.repository.repository_base import now_ts


class VocSpiderTaskStatus:
    """Task statuses for spider tasks (v1)."""

    PENDING = 10
    RUNNING = 20
    READY = 30
    FAILED = 40


class VocRepository:
    """VOC repository.

    Design rules:
    - CRUD only (no business judgment)
    - All timestamps are seconds int
    - No external IO
    """

    # -----------------
    # Jobs
    # -----------------

    @staticmethod
    async def create_job(
        db: AsyncSession,
        *,
        job_type: str,
        site_code: str,
        asin: Optional[str] = None,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        status: int = int(JobStatus.PENDING),
        max_retries: int = 3,
        created_by_user_id: Optional[int] = None,
    ) -> OpsVocJobsORM:
        job = OpsVocJobsORM(
            job_type=str(job_type),
            site_code=str(site_code),
            asin=asin,
            keyword=keyword,
            category=category,
            status=int(status),
            max_retries=int(max_retries),
            created_by_user_id=int(created_by_user_id) if created_by_user_id is not None else None,
        )
        db.add(job)
        await db.flush()
        return job

    @staticmethod
    async def get_job(db: AsyncSession, *, job_id: int) -> Optional[OpsVocJobsORM]:
        stmt = select(OpsVocJobsORM).where(OpsVocJobsORM.job_id == int(job_id))
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def claim_next_job(
        db: AsyncSession,
        *,
        worker_id: str,
        lease_seconds: int,
    ) -> Optional[OpsVocJobsORM]:
        """Claim one job for processing.

        Invariants:
        - Claimable: PENDING, FAILED(retryable), RUNNING(expired)
        - When claimed: status->RUNNING, locked_by/locked_until set, try_count++
        """
        now = now_ts()
        lease_until = now + int(lease_seconds)

        claimable = or_(
            OpsVocJobsORM.status == int(JobStatus.PENDING),
            and_(
                OpsVocJobsORM.status == int(JobStatus.FAILED),
                OpsVocJobsORM.try_count < OpsVocJobsORM.max_retries,
            ),
            and_(
                OpsVocJobsORM.status == int(JobStatus.RUNNING),
                or_(OpsVocJobsORM.locked_until.is_(None), OpsVocJobsORM.locked_until < now),
                OpsVocJobsORM.try_count < OpsVocJobsORM.max_retries,
            ),
        )

        # Only claim jobs whose spider task is READY and has run_id bound.
        # (Avoid claiming too early before spider callback arrives.)
        ready_task_exists = exists(
            select(1)
            .select_from(OpsVocJobSpiderTasksORM)
            .where(OpsVocJobSpiderTasksORM.job_id == OpsVocJobsORM.job_id)
            .where(OpsVocJobSpiderTasksORM.status == int(VocSpiderTaskStatus.READY))
            .where(OpsVocJobSpiderTasksORM.run_id.isnot(None))
        )

        stmt = (
            select(OpsVocJobsORM)
            .where(claimable)
            .where(ready_task_exists)
            .order_by(OpsVocJobsORM.job_id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        res = await db.execute(stmt)
        job = res.scalars().first()
        if job is None:
            return None

        job.status = int(JobStatus.RUNNING)
        job.locked_by = str(worker_id)
        job.locked_until = int(lease_until)
        job.try_count = int(job.try_count or 0) + 1
        job.updated_at = int(now)

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
            update(OpsVocJobsORM)
            .where(OpsVocJobsORM.job_id == int(job_id))
            .where(OpsVocJobsORM.status == int(JobStatus.RUNNING))
            .where(OpsVocJobsORM.locked_by == str(worker_id))
            .values(locked_until=int(lease_until), updated_at=int(now))
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
        report_id: Optional[int] = None,
        clear_lock: bool = True,
    ) -> int:
        values: dict[str, Any] = {"status": int(status), "updated_at": now_ts()}
        if last_error is not None:
            values["last_error"] = str(last_error)
        if report_id is not None:
            values["report_id"] = int(report_id)
        if clear_lock:
            values["locked_by"] = None
            values["locked_until"] = None

        stmt = update(OpsVocJobsORM).where(OpsVocJobsORM.job_id == int(job_id)).values(**values)
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    @staticmethod
    async def update_job_fields(
        db: AsyncSession,
        *,
        job_id: int,
        status: Optional[int] = None,
        last_error: Optional[str] = None,
        clear_last_error: bool = False,
        report_id: Optional[int] = None,
        locked_by: Optional[str] = None,
        locked_until: Optional[int] = None,
    ) -> int:
        values: dict[str, Any] = {"updated_at": now_ts()}
        if status is not None:
            values["status"] = int(status)
        if last_error is not None:
            values["last_error"] = str(last_error)
        elif clear_last_error:
            values["last_error"] = None
        if report_id is not None:
            values["report_id"] = int(report_id)
        if locked_by is not None:
            values["locked_by"] = str(locked_by)
        if locked_until is not None:
            values["locked_until"] = int(locked_until)

        if len(values) == 1:
            return 0

        stmt = update(OpsVocJobsORM).where(OpsVocJobsORM.job_id == int(job_id)).values(**values)
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    # -----------------
    # Spider tasks
    # -----------------

    @staticmethod
    async def create_spider_task(
        db: AsyncSession,
        *,
        job_id: int,
        task_id: str,
        run_type: str,
        site_code: str,
        asin: Optional[str] = None,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        status: int = VocSpiderTaskStatus.PENDING,
        callback_token_hash: str = "",
        callback_token_created_at: int = 0,
    ) -> OpsVocJobSpiderTasksORM:
        task = OpsVocJobSpiderTasksORM(
            job_id=int(job_id),
            task_id=str(task_id),
            run_type=str(run_type),
            site_code=str(site_code),
            asin=asin,
            keyword=keyword,
            category=category,
            status=int(status),
            callback_token_hash=str(callback_token_hash),
            callback_token_created_at=int(callback_token_created_at),
        )
        db.add(task)
        await db.flush()
        return task

    @staticmethod
    async def get_spider_task_by_task_id(db: AsyncSession, *, task_id: str) -> Optional[OpsVocJobSpiderTasksORM]:
        stmt = select(OpsVocJobSpiderTasksORM).where(OpsVocJobSpiderTasksORM.task_id == str(task_id))
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def list_spider_tasks_by_job(db: AsyncSession, *, job_id: int) -> List[OpsVocJobSpiderTasksORM]:
        stmt = (
            select(OpsVocJobSpiderTasksORM)
            .where(OpsVocJobSpiderTasksORM.job_id == int(job_id))
            .order_by(OpsVocJobSpiderTasksORM.task_row_id.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_spider_task(
        db: AsyncSession,
        *,
        task_id: str,
        status: Optional[int] = None,
        run_id: Optional[int] = None,
        last_error: Optional[str] = None,
        clear_last_error: bool = False,
    ) -> int:
        values: dict[str, Any] = {"updated_at": now_ts()}
        if status is not None:
            values["status"] = int(status)
        if run_id is not None:
            values["run_id"] = int(run_id)
        if last_error is not None:
            values["last_error"] = str(last_error)
        elif clear_last_error:
            values["last_error"] = None

        if len(values) == 1:
            return 0

        stmt = update(OpsVocJobSpiderTasksORM).where(OpsVocJobSpiderTasksORM.task_id == str(task_id)).values(**values)
        res = await db.execute(stmt)
        return int(res.rowcount or 0)

    # -----------------
    # Reports
    # -----------------

    @staticmethod
    async def create_report(
        db: AsyncSession,
        *,
        job_id: int,
        report_type: str,
        payload_json: dict[str, Any],
        meta_json: dict[str, Any],
    ) -> OpsVocReportsORM:
        # Idempotent behavior:
        # - If a report for this job already exists, update it in-place.
        # - Otherwise create a new one.
        # This avoids UNIQUE(job_id) violations when a job is re-run.

        existing = await VocRepository.get_report_by_job(db, job_id=int(job_id))
        if existing is not None:
            existing.report_type = str(report_type)
            existing.payload_json = dict(payload_json)
            existing.meta_json = dict(meta_json)
            existing.updated_at = now_ts()
            await db.flush()
            return existing

        report = OpsVocReportsORM(
            job_id=int(job_id),
            report_type=str(report_type),
            payload_json=dict(payload_json),
            meta_json=dict(meta_json),
        )
        db.add(report)
        try:
            await db.flush()
            return report
        except IntegrityError:
            # Rare race or manual DB edits: another row may have been created.
            await db.rollback()
            existing = await VocRepository.get_report_by_job(db, job_id=int(job_id))
            if existing is None:
                raise
            existing.report_type = str(report_type)
            existing.payload_json = dict(payload_json)
            existing.meta_json = dict(meta_json)
            existing.updated_at = now_ts()
            await db.flush()
            return existing

    @staticmethod
    async def get_report(db: AsyncSession, *, report_id: int) -> Optional[OpsVocReportsORM]:
        stmt = select(OpsVocReportsORM).where(OpsVocReportsORM.report_id == int(report_id))
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def get_report_by_job(db: AsyncSession, *, job_id: int) -> Optional[OpsVocReportsORM]:
        stmt = select(OpsVocReportsORM).where(OpsVocReportsORM.job_id == int(job_id))
        res = await db.execute(stmt)
        return res.scalars().first()
