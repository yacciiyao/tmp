# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC service (review analysis job creation + spider callback handling)

from __future__ import annotations

import hashlib
import re
import secrets
import time
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from domains.error_domain import AppError, NotFoundError, ValidationAppError
from domains.rag_domain import JobStatus
from infrastructures.db.repository.voc_repository import VocRepository, VocSpiderTaskStatus
from infrastructures.spider.spider_client import build_review_spider_payload, enqueue_spider_task
from infrastructures.vconfig import vconfig
from infrastructures.vlogger import vlogger


_ASIN_RE = re.compile(r"^[A-Z0-9]{8,12}$", re.IGNORECASE)


class VocJobType:
    REVIEW_ANALYSIS = "review_analysis"


class VocRunType:
    AMAZON_REVIEW = "amazon_review"


def _normalize_site_code(site_code: str) -> str:
    return site_code.strip().upper()


def _normalize_asin(asin: str) -> str:
    return asin.strip().upper()


def _callback_url() -> str:
    base = (vconfig.public_base_url or "").strip().rstrip("/")
    if not base:
        raise AppError(
            code="voc.public_base_url_missing",
            message="PUBLIC_BASE_URL is empty. Please set it in .env for spider callback URL.",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return f"{base}/voc/spider/callback"


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class VocService:
    """VOC service.

    Rules:
    - Service orchestrates; DB is accessed only via repository.
    - External systems are called only via infrastructure helpers.
    - Deterministic: user input is explicit; no implicit lookup of "latest".
    """

    def __init__(self, *, repo: VocRepository) -> None:
        self._repo = repo

    async def get_job(self, db: AsyncSession, *, job_id: int):
        """Get job by id (router should remain thin)."""
        return await self._repo.get_job(db, job_id=int(job_id))

    async def get_report(self, db: AsyncSession, *, report_id: int):
        """Get report by report_id."""
        return await self._repo.get_report(db, report_id=int(report_id))

    async def get_report_by_job(self, db: AsyncSession, *, job_id: int):
        """Get report by job_id (1 job -> 1 report)."""
        return await self._repo.get_report_by_job(db, job_id=int(job_id))

    async def create_review_analysis_job(
        self,
        db: AsyncSession,
        *,
        site_code: str,
        asin: str,
        created_by_user_id: Optional[int] = None,
    ) -> Tuple[int, int, Optional[int]]:
        """Create a review analysis job and enqueue a spider task.

        Invariants:
            - job_type fixed to REVIEW_ANALYSIS
            - one job -> one spider task (amazon_review)
            - task_id deterministic: voc:{job_id}:amazon_review
        """
        sc = _normalize_site_code(site_code)
        a = _normalize_asin(asin)
        if not sc:
            raise ValidationAppError(message="site_code is required")
        if not a:
            raise ValidationAppError(message="asin is required")
        if not _ASIN_RE.match(a):
            raise ValidationAppError(message="asin format invalid", details={"asin": a})

        cb = _callback_url()

        # One-time callback token per task (plain text sent to spider, hash stored in app_db)
        callback_token = secrets.token_hex(16)  # 32 hex chars
        callback_token_hash = _sha256_hex(callback_token)

        job = await self._repo.create_job(
            db,
            job_type=VocJobType.REVIEW_ANALYSIS,
            site_code=sc,
            asin=a,
            keyword=None,
            category=None,
            status=int(JobStatus.PENDING),
            max_retries=3,
            created_by_user_id=created_by_user_id,
        )

        task_id = f"voc:{int(job.job_id)}:{VocRunType.AMAZON_REVIEW}"
        await self._repo.create_spider_task(
            db,
            job_id=int(job.job_id),
            task_id=task_id,
            run_type=VocRunType.AMAZON_REVIEW,
            site_code=sc,
            asin=a,
            keyword=None,
            category=None,
            status=VocSpiderTaskStatus.PENDING,
            callback_token_hash=callback_token_hash,
            callback_token_created_at=int(time.time()),
        )

        payload = build_review_spider_payload(
            task_id=task_id,
            site_code=sc,
            asin=a,
            callback_url=cb,
            callback_token=callback_token,
            extra={"job_id": int(job.job_id), "job_type": VocJobType.REVIEW_ANALYSIS},
        )

        await enqueue_spider_task(payload)

        vlogger.info(
            "voc job created",
            extra={"job_id": int(job.job_id), "job_type": VocJobType.REVIEW_ANALYSIS, "task_id": task_id},
        )
        return int(job.job_id), int(job.status), job.report_id

    async def handle_spider_callback(
        self,
        db: AsyncSession,
        *,
        task_id: str,
        status_text: str,
        run_id: Optional[int] = None,
        error: Optional[str] = None,
        callback_token: Optional[str] = None,
    ) -> Tuple[int, int]:
        """Handle spider completion callback.

        Policy (v1):
            - READY: spider_task->READY + run_id，job 仍为 PENDING（等 worker 分析）
            - FAILED: spider_task->FAILED，同时 job->FAILED 以便立刻可见
        """
        tid = (task_id or "").strip()
        if not tid:
            raise ValidationAppError(message="task_id is required")

        st = (status_text or "").strip().upper()
        if st not in ("READY", "FAILED", "RUNNING"):
            raise ValidationAppError(message="status invalid", details={"status": status_text})

        task = await self._repo.get_spider_task_by_task_id(db, task_id=tid)
        if task is None:
            raise NotFoundError(message="spider task not found", details={"task_id": tid})

        token_plain = (callback_token or "").strip()
        if not token_plain:
            raise ValidationAppError(message="callback_token is required")

        token_hash = _sha256_hex(token_plain)
        if not task.callback_token_hash or token_hash != task.callback_token_hash:
            raise AppError(
                code="voc.callback_token_invalid",
                message="Invalid callback token",
                http_status=status.HTTP_401_UNAUTHORIZED,
                details={"task_id": tid},
            )

        if st == "RUNNING":
            updated_tasks = await self._repo.update_spider_task(
                db,
                task_id=tid,
                status=VocSpiderTaskStatus.RUNNING,
                run_id=run_id,
                clear_last_error=True,
            )
            return int(updated_tasks), 0

        if st == "READY":
            if run_id is None or int(run_id) <= 0:
                raise ValidationAppError(message="run_id is required when status=READY")
            updated_tasks = await self._repo.update_spider_task(
                db,
                task_id=tid,
                status=VocSpiderTaskStatus.READY,
                run_id=int(run_id),
                clear_last_error=True,
            )
            updated_jobs = await self._repo.update_job_fields(
                db,
                job_id=int(task.job_id),
                status=int(JobStatus.PENDING),
                clear_last_error=True,
            )
            vlogger.info("spider task ready", extra={"task_id": tid, "job_id": int(task.job_id), "run_id": int(run_id)})
            return int(updated_tasks), int(updated_jobs)

        # FAILED
        err = (error or "").strip() or "SPIDER_FAILED"
        updated_tasks = await self._repo.update_spider_task(
            db,
            task_id=tid,
            status=VocSpiderTaskStatus.FAILED,
            run_id=run_id,
            last_error=err,
        )
        updated_jobs = await self._repo.update_job_fields(
            db,
            job_id=int(task.job_id),
            status=int(JobStatus.FAILED),
            last_error=err,
        )
        vlogger.warning("spider task failed", extra={"task_id": tid, "job_id": int(task.job_id), "error": err})
        return int(updated_tasks), int(updated_jobs)
