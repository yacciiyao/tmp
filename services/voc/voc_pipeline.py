# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC worker pipeline (extract -> analyze -> persist).

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from domains.voc_job_domain import VocJobStage, VocJobStatus
from infrastructures.db.repository.spider_results_repository import SpiderResultsRepository
from infrastructures.db.repository.voc_repository import VocRepository
from infrastructures.db.spider_orm.spider_orm_base import SpiderAsyncSessionFactory
from infrastructures.vlogger import vlogger


@dataclass
class VocRunResult:
    status: str  # SUCCEEDED|RETRYABLE|FAILED
    message: str = ""
    data: Optional[Dict[str, Any]] = None


class VocPipeline:
    """Minimal VOC pipeline.

    This pipeline is intentionally conservative:
      - It only validates that we can load datasets from spider results DB
      - It writes a single debug output snapshot
      - It leaves all business analyzers for the next iteration
    """

    def __init__(self, *, repo: Optional[VocRepository] = None) -> None:
        self.repo = repo or VocRepository()

    async def run_job(self, db: AsyncSession, *, job_id: int, worker_id: str) -> VocRunResult:
        job = await self.repo.get_job(db, job_id=int(job_id))
        if job is None:
            return VocRunResult(status="FAILED", message=f"job {job_id} not found")

        params = dict(job.params_json or {})
        site_code = str(job.site_code)
        target_asins = list(params.get("target_asins") or [])
        competitor_asins = list(params.get("competitor_asins") or [])
        keywords = list(params.get("keywords") or [])

        asins = sorted(set([str(a) for a in (target_asins + competitor_asins) if str(a).strip()]))
        keywords = sorted(set([str(k) for k in keywords if str(k).strip()]))

        # progress job
        await self.repo.update_job_status(db, job_id=int(job_id), status=int(VocJobStatus.ANALYZING), stage=VocJobStage.analyzing.value)

        now_ts = int(datetime.now(timezone.utc).timestamp())
        tw = dict(params.get("time_window") or {})
        reviews_days = int(tw.get("reviews_days") or 365)

        review_time_from = now_ts - int(reviews_days) * 86400

        try:
            async with SpiderAsyncSessionFactory() as spider_db:
                review_ds = await SpiderResultsRepository.load_review_dataset(
                    spider_db,
                    site_code=site_code,
                    asins=asins,
                    review_time_from=review_time_from,
                    review_time_to=now_ts,
                    preferred_task_id=job.preferred_task_id,
                    preferred_run_id=job.preferred_run_id,
                )

                listing_ds = await SpiderResultsRepository.load_listing_dataset(
                    spider_db,
                    site_code=site_code,
                    asins=asins,
                    preferred_task_id=job.preferred_task_id,
                    preferred_run_id=job.preferred_run_id,
                    mode="latest_common_day",
                )

                kw_ds = await SpiderResultsRepository.load_keyword_serp_dataset(
                    spider_db,
                    site_code=site_code,
                    keywords=keywords,
                    preferred_task_id=job.preferred_task_id,
                    preferred_run_id=job.preferred_run_id,
                    mode="latest_common_day",
                )

                latest_listing_map = await SpiderResultsRepository.get_latest_listing_day_map(spider_db, site_code=site_code, asins=asins)
                latest_kw_map = await SpiderResultsRepository.get_latest_keyword_day_map(spider_db, site_code=site_code, keywords=keywords)

            payload: Dict[str, Any] = {
                "site_code": site_code,
                "asins": asins,
                "keywords": keywords,
                "datasets": {
                    "reviews": {
                        "count": len(review_ds.reviews),
                        "time_from": review_time_from,
                        "time_to": now_ts,
                    },
                    "listings": {
                        "snapshots": len(listing_ds.snapshots),
                        "start_day": listing_ds.start_day,
                        "end_day": listing_ds.end_day,
                        "latest_day_map": latest_listing_map,
                    },
                    "keyword_serp": {
                        "items": len(kw_ds.items),
                        "start_day": kw_ds.start_day,
                        "end_day": kw_ds.end_day,
                        "latest_day_map": latest_kw_map,
                    },
                },
                "preferred": {
                    "preferred_task_id": job.preferred_task_id,
                    "preferred_run_id": job.preferred_run_id,
                },
                "worker_id": worker_id,
            }

            await self.repo.upsert_output(db, job_id=int(job_id), module_code="debug.datasets", payload_json=payload, schema_version=1)

            await self.repo.update_job_status(db, job_id=int(job_id), status=int(VocJobStatus.DONE), stage=None)
            await self.repo.clear_job_lease(db, job_id=int(job_id))

            vlogger.info("voc job done", extra={"job_id": int(job_id), "worker_id": worker_id})
            return VocRunResult(status="SUCCEEDED")
        except Exception as e:
            vlogger.exception("voc job failed", extra={"job_id": int(job_id), "worker_id": worker_id})
            await self.repo.update_job_status(
                db,
                job_id=int(job_id),
                status=int(VocJobStatus.FAILED),
                stage=None,
                error_code="voc.pipeline_error",
                error_message=str(e),
                failed_stage=VocJobStage.analyzing.value,
            )
            await self.repo.clear_job_lease(db, job_id=int(job_id))
            return VocRunResult(status="FAILED", message=str(e))
