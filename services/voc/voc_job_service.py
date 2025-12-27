# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC job service (MVP: reviews closed loop)

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from domains.error_domain import AppError
from domains.voc_domain import VocJobStatus
from domains.voc_output_domain import VocEvidenceItem
from infrastructures.db.repository.spider_results_repository import SpiderResultsRepository
from infrastructures.db.repository.voc_repository import VocRepository
from services.voc.review_analyzer import ReviewOverviewAnalyzer


def _stable_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class VocJobService:
    """VOC application service.

    v1 scope:
    - only review jobs (scope_type=asin_set)
    - synchronous pipeline execution (for MVP)
    """

    # -----------------------------
    # Job API
    # -----------------------------

    async def get_job(self, db: AsyncSession, *, job_id: int):
        return await VocRepository.get_job(db, job_id=int(job_id))

    async def list_outputs(self, db: AsyncSession, *, job_id: int):
        return await VocRepository.list_outputs(db, job_id=int(job_id))

    async def get_output(self, db: AsyncSession, *, job_id: int, module_code: str):
        return await VocRepository.get_output(db, job_id=int(job_id), module_code=str(module_code))

    async def list_evidence(self, db: AsyncSession, *, job_id: int, module_code: Optional[str] = None) -> List[VocEvidenceItem]:
        rows = await VocRepository.list_evidence(db, job_id=int(job_id), module_code=module_code)
        return [
            VocEvidenceItem(
                evidence_id=int(r.evidence_id),
                job_id=int(r.job_id),
                module_code=str(r.module_code),
                source_type=str(r.source_type),
                source_id=int(r.source_id),
                kind=str(r.kind) if r.kind is not None else None,
                snippet=str(r.snippet),
                meta_json=dict(r.meta_json or {}),
                created_at=int(r.created_at),
                updated_at=int(r.updated_at),
            )
            for r in rows
        ]

    async def create_or_reuse_review_job(self, db: AsyncSession, *, site_code: str, asins: List[str], review_days: int):
        if not asins:
            raise AppError(code="voc.invalid_input", message="asins is empty", http_status=400)

        site_code = str(site_code).upper().strip()
        asins = sorted({str(a).strip() for a in asins if str(a).strip()})
        if not asins:
            raise AppError(code="voc.invalid_input", message="asins is empty", http_status=400)

        # keep scope_value stable and within 256 chars
        asin_digest = _sha256_hex(",".join(asins))[:32]
        scope_type = "asin_set"
        scope_value = asin_digest

        params = {
            "site_code": site_code,
            "asins": asins,
            "review_days": int(review_days),
        }

        input_hash = _sha256_hex(f"voc:reviews:{site_code}:{scope_type}:{scope_value}:{_stable_json(params)}")

        existing = await VocRepository.get_job_by_hash(db, input_hash=input_hash)
        if existing is not None:
            return existing

        job = await VocRepository.create_job(
            db,
            input_hash=input_hash,
            site_code=site_code,
            scope_type=scope_type,
            scope_value=scope_value,
            params_json=params,
            status=int(VocJobStatus.PENDING),
            stage=None,
        )
        # commit early so that even if pipeline fails later, job_id exists.
        await db.commit()
        return job

    # -----------------------------
    # Pipeline
    # -----------------------------

    async def run_review_job_pipeline(self, *, db: AsyncSession, spider_db: AsyncSession, job_id: int) -> None:
        job = await VocRepository.get_job(db, job_id=int(job_id))
        if job is None:
            raise AppError(code="voc.job_not_found", message=f"job_id={job_id} not found", http_status=404)

        if int(job.status) == int(VocJobStatus.DONE):
            return

        last_stage: str | None = None

        try:
            # ---------- extracting ----------
            last_stage = "extracting"
            await VocRepository.update_job_status(db, job_id=int(job_id), status=int(VocJobStatus.EXTRACTING), stage=last_stage)
            await db.commit()

            params = dict(job.params_json or {})
            site_code = str(params.get("site_code") or job.site_code)
            asins = list(params.get("asins") or [])
            review_days = int(params.get("review_days") or 365)

            now_ts = int(time.time())
            review_time_from = now_ts - review_days * 86400
            review_time_to = now_ts

            ds = await SpiderResultsRepository.load_review_dataset(
                spider_db,
                site_code=site_code,
                asins=asins,
                review_time_from=review_time_from,
                review_time_to=review_time_to,
                preferred_task_id=job.preferred_task_id,
                preferred_run_id=job.preferred_run_id,
            )

            # ---------- analyzing ----------
            last_stage = "analyzing"
            await VocRepository.update_job_status(db, job_id=int(job_id), status=int(VocJobStatus.ANALYZING), stage=last_stage)
            await db.commit()

            result = ReviewOverviewAnalyzer.compute(ds=ds, days_for_trend=30)

            # ---------- persisting ----------
            last_stage = "persisting"
            await VocRepository.update_job_status(db, job_id=int(job_id), status=int(VocJobStatus.PERSISTING), stage=last_stage)
            await db.commit()

            # outputs
            await VocRepository.upsert_output(
                db,
                job_id=int(job_id),
                module_code=result.output.module_code,
                payload_json=result.output.model_dump(),
                schema_version=int(result.output.schema_version),
            )

            # evidence (append-only for v1)
            await VocRepository.clear_evidence(db, job_id=int(job_id), module_code=result.output.module_code)
            ev_items = []
            for e in result.evidence_rows:
                ev_items.append({
                    "source_type": e["source_type"],
                    "source_id": e["source_id"],
                    "kind": e.get("kind"),
                    "snippet": e.get("snippet") or "",
                    "meta_json": e.get("meta_json") or {},
                })
            await VocRepository.insert_evidence_many(
                db,
                job_id=int(job_id),
                module_code=result.output.module_code,
                items=ev_items,
            )

            await db.commit()

            # ---------- done ----------
            last_stage = "done"
            await VocRepository.update_job_status(db, job_id=int(job_id), status=int(VocJobStatus.DONE), stage=last_stage)
            await db.commit()

        except AppError:
            raise
        except Exception as e:
            await VocRepository.update_job_status(
                db,
                job_id=int(job_id),
                status=int(VocJobStatus.FAILED),
                stage="failed",
                error_code="voc.pipeline_error",
                error_message=str(e),
                failed_stage=last_stage,
            )
            await db.commit()
            raise
