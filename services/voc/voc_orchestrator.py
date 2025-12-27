# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC orchestration logic: decide crawl plan, enqueue spider tasks, handle callbacks.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.error_domain import AppError
from domains.voc_job_domain import CreateVocJobRequest, SpiderCallbackRequest, VocJobStage, VocJobStatus
from infrastructures.db.repository.spider_results_repository import SpiderResultsRepository
from infrastructures.db.repository.voc_repository import VocRepository
from infrastructures.db.spider_orm.spider_orm_base import SpiderAsyncSessionFactory
from infrastructures.spider.spider_client import enqueue_spider_task
from infrastructures.spider.spider_payloads import build_keyword_payload, build_listing_payload, build_review_payload
from infrastructures.vconfig import vconfig
from infrastructures.vlogger import vlogger
from services.voc.security import build_callback_token, verify_callback_token
from services.voc.voc_job_service import VocJobService


def _utc_day(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _is_day_fresh(day: Optional[str], *, threshold_day: str) -> bool:
    if day is None:
        return False
    return str(day) >= str(threshold_day)


@dataclass
class CrawlUnit:
    run_type: str
    scope_type: str
    scope_value: str


class VocOrchestrator:
    def __init__(self, *, repo: Optional[VocRepository] = None, job_service: Optional[VocJobService] = None) -> None:
        self.repo = repo or VocRepository()
        self.job_service = job_service or VocJobService(repo=self.repo)

    async def create_or_start_job(self, db: AsyncSession, *, req: CreateVocJobRequest) -> int:
        """Create/reuse a VOC job, then decide whether to crawl.

        Returns:
            job_id
        """

        job = await self.job_service.create_or_get_job(db, req=req)

        # Already done or running: do not restart automatically
        if int(job.status) in (int(VocJobStatus.CRAWLING), int(VocJobStatus.EXTRACTING), int(VocJobStatus.ANALYZING), int(VocJobStatus.PERSISTING)):
            return int(job.job_id)
        if int(job.status) == int(VocJobStatus.DONE):
            return int(job.job_id)

        trigger_mode = str((job.params_json or {}).get("trigger_mode") or "AUTO").upper()

        # OFF => skip crawl, go directly to extracting
        if trigger_mode == "OFF":
            await self.repo.update_job_status(db, job_id=int(job.job_id), status=int(VocJobStatus.EXTRACTING), stage=VocJobStage.extracting.value)
            return int(job.job_id)

        crawl_units = await self._decide_crawl_units(
            job_id=int(job.job_id),
            site_code=str(job.site_code),
            params_json=dict(job.params_json or {}),
            trigger_mode=trigger_mode,
        )
        if not crawl_units:
            await self.repo.update_job_status(db, job_id=int(job.job_id), status=int(VocJobStatus.EXTRACTING), stage=VocJobStage.extracting.value)
            return int(job.job_id)

        # enqueue
        if not str(vconfig.public_base_url).strip():
            raise AppError(
                code="voc.missing_public_base_url",
                message="PUBLIC_BASE_URL is required to build spider callback URLs",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        cb_token = build_callback_token(job_id=int(job.job_id))
        pending = []
        for u in crawl_units:
            cb_url = self._build_callback_url(job_id=int(job.job_id), unit=u)
            payload = self._build_payload_for_unit(task_id=f"voc:{job.job_id}:{u.run_type}:{u.scope_value}", site_code=str(job.site_code), cb_url=cb_url, cb_token=cb_token, unit=u)
            await enqueue_spider_task(payload)
            pending.append({"run_type": u.run_type, "scope_type": u.scope_type, "scope_value": u.scope_value})

        # store pending crawl plan into params_json
        new_params = dict(job.params_json or {})
        new_params["pending_crawl"] = pending
        await self.repo.update_job_params_json(db, job_id=int(job.job_id), params_json=new_params)

        await self.repo.update_job_status(db, job_id=int(job.job_id), status=int(VocJobStatus.CRAWLING), stage=VocJobStage.crawling.value)
        vlogger.info("voc job enqueued spider tasks", extra={"job_id": int(job.job_id), "pending": len(pending)})
        return int(job.job_id)

    async def handle_spider_callback(
        self,
        db: AsyncSession,
        *,
        job_id: int,
        token: str | None,
        req: SpiderCallbackRequest,
        run_type: Optional[str] = None,
        scope_type: Optional[str] = None,
        scope_value: Optional[str] = None,
    ) -> None:
        if not verify_callback_token(job_id=int(job_id), token=token):
            raise AppError(code="voc.invalid_callback_token", message="Invalid callback token", http_status=401)

        job = await self.repo.get_job(db, job_id=int(job_id))
        if job is None:
            raise AppError(code="voc.job_not_found", message=f"Job {job_id} not found", http_status=404)

        status_str = str(req.status or "").upper()
        ok = status_str in ("SUCCESS", "SUCCEEDED", "DONE", "OK")

        # persist pointers if provided
        await self.repo.set_preferred_spider_ids(
            db,
            job_id=int(job_id),
            preferred_task_id=int(req.task_id) if req.task_id is not None else None,
            preferred_run_id=int(req.run_id) if req.run_id is not None else None,
        )

        if not ok:
            await self.repo.update_job_status(
                db,
                job_id=int(job_id),
                status=int(VocJobStatus.FAILED),
                stage=None,
                error_code=req.error_code or "spider.failed",
                error_message=req.error_message or "spider callback failed",
                failed_stage=VocJobStage.crawling.value,
            )
            return

        # idempotency: if already progressed beyond crawling, do nothing
        if int(job.status) in (int(VocJobStatus.EXTRACTING), int(VocJobStatus.ANALYZING), int(VocJobStatus.PERSISTING), int(VocJobStatus.DONE)):
            return

        # mark one crawl unit as finished
        params = dict(job.params_json or {})
        pending: List[Dict[str, Any]] = list(params.get("pending_crawl") or [])
        if pending and run_type and scope_type and scope_value:
            pending = [p for p in pending if not (p.get("run_type") == run_type and p.get("scope_type") == scope_type and p.get("scope_value") == scope_value)]
            params["pending_crawl"] = pending
            await self.repo.update_job_params_json(db, job_id=int(job_id), params_json=params)

        if pending:
            # still waiting for other units
            return

        await self.repo.update_job_status(db, job_id=int(job_id), status=int(VocJobStatus.EXTRACTING), stage=VocJobStage.extracting.value)

    # -----------------------------
    # Internals
    # -----------------------------

    async def _decide_crawl_units(self, *, job_id: int, site_code: str, params_json: Dict[str, Any], trigger_mode: str) -> List[CrawlUnit]:
        target_asins = list(params_json.get("target_asins") or [])
        competitor_asins = list(params_json.get("competitor_asins") or [])
        keywords = list(params_json.get("keywords") or [])

        asins = sorted(set([str(a) for a in (target_asins + competitor_asins) if str(a).strip()]))
        keywords = sorted(set([str(k) for k in keywords if str(k).strip()]))

        if trigger_mode == "FORCE":
            units = []
            for a in asins:
                units.append(CrawlUnit(run_type="amazon_listing", scope_type="asin", scope_value=a))
                units.append(CrawlUnit(run_type="amazon_review", scope_type="asin", scope_value=a))
            for k in keywords:
                units.append(CrawlUnit(run_type="amazon_keyword_search", scope_type="keyword", scope_value=k))
            return units

        # AUTO freshness check (listing+keyword only)
        threshold_day = _utc_day(datetime.now(timezone.utc) - timedelta(days=1))
        units: List[CrawlUnit] = []

        async with SpiderAsyncSessionFactory() as spider_db:
            if asins:
                latest_map = await SpiderResultsRepository.get_latest_listing_day_map(spider_db, site_code=str(site_code), asins=asins)
                for a in asins:
                    if not _is_day_fresh(latest_map.get(a), threshold_day=threshold_day):
                        units.append(CrawlUnit(run_type="amazon_listing", scope_type="asin", scope_value=a))

            if keywords:
                latest_kw_map = await SpiderResultsRepository.get_latest_keyword_day_map(spider_db, site_code=str(site_code), keywords=keywords)
                for k in keywords:
                    if not _is_day_fresh(latest_kw_map.get(k), threshold_day=threshold_day):
                        units.append(CrawlUnit(run_type="amazon_keyword_search", scope_type="keyword", scope_value=k))

        # review is incremental; default to not force-crawl in AUTO
        return units

    def _build_callback_url(self, *, job_id: int, unit: CrawlUnit) -> str:
        base = str(vconfig.public_base_url).rstrip("/")
        q_run_type = quote(unit.run_type, safe="")
        q_scope_type = quote(unit.scope_type, safe="")
        q_scope_value = quote(unit.scope_value, safe="")
        return f"{base}/voc/spider/callback/{int(job_id)}?run_type={q_run_type}&scope_type={q_scope_type}&scope_value={q_scope_value}"

    @staticmethod
    def _build_payload_for_unit(*, task_id: str, site_code: str, cb_url: str, cb_token: str, unit: CrawlUnit) -> Dict[str, Any]:
        if unit.run_type == "amazon_review":
            return build_review_payload(task_id=task_id, site_code=site_code, asin=unit.scope_value, callback_url=cb_url, callback_token=cb_token)
        if unit.run_type == "amazon_listing":
            return build_listing_payload(task_id=task_id, site_code=site_code, asin=unit.scope_value, callback_url=cb_url, callback_token=cb_token)
        if unit.run_type == "amazon_keyword_search":
            return build_keyword_payload(task_id=task_id, site_code=site_code, keyword=unit.scope_value, callback_url=cb_url, callback_token=cb_token)

        raise AppError(code="voc.unsupported_run_type", message=f"Unsupported run_type: {unit.run_type}", http_status=400)
