# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC job service (reviews + market + keyword + report v1)

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from domains.error_domain import AppError
from domains.voc_domain import VocJobStatus
from domains.voc_output_domain import VocEvidenceItem
from infrastructures.db.repository.spider_results_repository import SpiderResultsRepository
from infrastructures.db.repository.voc_repository import VocRepository

# review analyzers
from services.voc.review_analyzer import ReviewOverviewAnalyzer
from services.voc.review_customer_sentiment_analyzer import ReviewCustomerSentimentAnalyzer
from services.voc.review_usage_scenario_analyzer import ReviewUsageScenarioAnalyzer
from services.voc.review_buyers_motivation_analyzer import ReviewBuyersMotivationAnalyzer
from services.voc.review_customer_expectations_analyzer import ReviewCustomerExpectationsAnalyzer
from services.voc.review_rating_optimization_analyzer import ReviewRatingOptimizationAnalyzer

# market/keyword analyzers
from services.voc.market_product_details_analyzer import MarketProductDetailsAnalyzer
from services.voc.keyword_details_analyzer import KeywordDetailsAnalyzer

# report
from services.voc.report_v1_builder import ReportV1Builder


def _stable_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _norm_list(xs: Optional[Sequence[str]]) -> List[str]:
    return sorted({str(x).strip() for x in (xs or []) if str(x).strip()})


class VocJobService:
    """VOC application service.

    Current capabilities:
    - review modules (6)
    - market.product_details (listing snapshot)
    - keyword.keyword_details (SERP snapshot)
    - report.v1 aggregation (outputs/evidence only)

    Notes:
    - Spider(results) DB is treated as read-only.
    - Jobs are idempotent by input_hash.
    """

    # -----------------------------
    # Job read APIs
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

    # -----------------------------
    # Job creation APIs
    # -----------------------------

    async def create_or_reuse_review_job(self, db: AsyncSession, *, site_code: str, asins: List[str], review_days: int):
        """Keep backward-compatible review-only job creation."""
        if not asins:
            raise AppError(code="voc.invalid_input", message="asins is empty", http_status=400)

        site_code = str(site_code).upper().strip()
        asins = _norm_list(asins)
        if not asins:
            raise AppError(code="voc.invalid_input", message="asins is empty", http_status=400)

        asin_digest = _sha256_hex(",".join(asins))[:32]
        scope_type = "asin_set"
        scope_value = asin_digest

        params = {
            "site_code": site_code,
            "asins": asins,
            "review_days": int(review_days),
            # keep extensibility: review-only job has no competitors/keywords by default
            "competitor_asins": [],
            "keywords": [],
            "max_serp_page_num": None,
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
        await db.commit()
        return job

    async def create_or_reuse_voc_job(
        self,
        db: AsyncSession,
        *,
        site_code: str,
        asins: Optional[Sequence[str]] = None,
        competitor_asins: Optional[Sequence[str]] = None,
        keywords: Optional[Sequence[str]] = None,
        review_days: int = 365,
        max_serp_page_num: Optional[int] = 2,
    ):
        """Create or reuse a VOC bundle job (reviews + market + keyword + report).

        - asins: target products
        - competitor_asins: optional competitor products
        - keywords: optional keywords to analyze SERP
        """

        site_code = str(site_code).upper().strip()
        target_asins = _norm_list(asins)
        comp_asins = _norm_list(competitor_asins)
        kws = _norm_list(keywords)

        if not target_asins and not comp_asins and not kws:
            raise AppError(code="voc.invalid_input", message="asins/competitor_asins/keywords all empty", http_status=400)

        scope_type = "voc_bundle"
        scope_value = _sha256_hex(",".join(target_asins) + "|" + ",".join(comp_asins) + "|" + ",".join(kws))[:32]

        params: Dict[str, Any] = {
            "site_code": site_code,
            "asins": target_asins,
            "competitor_asins": comp_asins,
            "keywords": kws,
            "review_days": int(review_days),
            "max_serp_page_num": int(max_serp_page_num) if max_serp_page_num is not None else None,
        }

        input_hash = _sha256_hex(f"voc:bundle:{site_code}:{scope_type}:{scope_value}:{_stable_json(params)}")

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
        await db.commit()
        return job

    async def enqueue_job(self, db: AsyncSession, *, job_id: int) -> None:
        """Mark an existing job as queued for VOC worker."""

        job = await VocRepository.get_job(db, job_id=int(job_id))
        if job is None:
            raise AppError(code="voc.job_not_found", message=f"job_id={job_id} not found", http_status=404)

        if int(job.status) in (int(VocJobStatus.DONE), int(VocJobStatus.FAILED)):
            return

        if int(job.status) == int(VocJobStatus.PENDING):
            await VocRepository.update_job_status(
                db,
                job_id=int(job_id),
                status=int(VocJobStatus.EXTRACTING),
                stage="queued",
                error_code=None,
                error_message=None,
                failed_stage=None,
            )
            await db.commit()

    # Backward-compatible alias
    async def enqueue_review_job(self, db: AsyncSession, *, job_id: int) -> None:
        return await self.enqueue_job(db, job_id=int(job_id))

    # -----------------------------
    # Pipeline
    # -----------------------------

    async def run_review_job_pipeline(self, *, db: AsyncSession, spider_db: AsyncSession, job_id: int) -> None:
        """Backward-compatible alias."""
        await self.run_job_pipeline(db=db, spider_db=spider_db, job_id=int(job_id))

    async def run_job_pipeline(self, *, db: AsyncSession, spider_db: AsyncSession, job_id: int) -> None:
        job = await VocRepository.get_job(db, job_id=int(job_id))
        if job is None:
            raise AppError(code="voc.job_not_found", message=f"job_id={job_id} not found", http_status=404)

        if int(job.status) == int(VocJobStatus.DONE):
            return

        last_stage: str | None = None

        async def _persist_module(*, module_code: str, output_payload: Dict[str, Any], schema_version: int, evidence_rows: List[Dict[str, Any]]):
            await VocRepository.upsert_output(
                db,
                job_id=int(job_id),
                module_code=module_code,
                payload_json=output_payload,
                schema_version=int(schema_version),
            )
            await VocRepository.clear_evidence(db, job_id=int(job_id), module_code=module_code)
            ev_items = []
            for e in evidence_rows or []:
                ev_items.append(
                    {
                        "source_type": e["source_type"],
                        "source_id": e["source_id"],
                        "kind": e.get("kind"),
                        "snippet": e.get("snippet") or "",
                        "meta_json": e.get("meta_json") or {},
                    }
                )
            await VocRepository.insert_evidence_many(db, job_id=int(job_id), module_code=module_code, items=ev_items)

        try:
            # ---------- extracting ----------
            last_stage = "extracting"
            await VocRepository.update_job_status(db, job_id=int(job_id), status=int(VocJobStatus.EXTRACTING), stage=last_stage)
            await db.commit()

            params = dict(job.params_json or {})
            site_code = str(params.get("site_code") or job.site_code).upper()

            target_asins = _norm_list(params.get("asins"))
            competitor_asins = _norm_list(params.get("competitor_asins"))
            keywords = _norm_list(params.get("keywords"))

            review_days = int(params.get("review_days") or 365)
            max_serp_page_num = params.get("max_serp_page_num")
            max_serp_page_num = int(max_serp_page_num) if max_serp_page_num is not None else None

            # datasets
            review_ds = None
            listing_ds = None
            keyword_ds = None

            now_ts = int(time.time())

            if target_asins:
                review_time_from = now_ts - review_days * 86400
                review_time_to = now_ts
                review_ds = await SpiderResultsRepository.load_review_dataset(
                    spider_db,
                    site_code=site_code,
                    asins=target_asins,
                    review_time_from=review_time_from,
                    review_time_to=review_time_to,
                    preferred_task_id=job.preferred_task_id,
                    preferred_run_id=job.preferred_run_id,
                )

            listing_asins = sorted({*set(target_asins), *set(competitor_asins)})
            if listing_asins:
                listing_ds = await SpiderResultsRepository.load_listing_dataset(
                    spider_db,
                    site_code=site_code,
                    asins=listing_asins,
                    preferred_task_id=job.preferred_task_id,
                    preferred_run_id=job.preferred_run_id,
                    mode="latest_common_day",
                )

            if keywords:
                keyword_ds = await SpiderResultsRepository.load_keyword_serp_dataset(
                    spider_db,
                    site_code=site_code,
                    keywords=keywords,
                    preferred_task_id=job.preferred_task_id,
                    preferred_run_id=job.preferred_run_id,
                    mode="latest_common_day",
                    max_page_num=max_serp_page_num,
                )

            # ---------- analyzing ----------
            last_stage = "analyzing"
            await VocRepository.update_job_status(db, job_id=int(job_id), status=int(VocJobStatus.ANALYZING), stage=last_stage)
            await db.commit()

            # compute modules (in-memory)
            computed: List[tuple[str, Dict[str, Any], int, List[Dict[str, Any]]]] = []

            if review_ds is not None:
                result = ReviewOverviewAnalyzer.compute(ds=review_ds, days_for_trend=30)
                sentiment = ReviewCustomerSentimentAnalyzer.compute(ds=review_ds, top_k=12, max_evidence_per_topic=5)
                usage = ReviewUsageScenarioAnalyzer.compute(ds=review_ds, top_k=12, max_evidence_per_scenario=6)
                motivation = ReviewBuyersMotivationAnalyzer.compute(ds=review_ds, top_k=12, max_evidence_per_motivation=6)
                expectations = ReviewCustomerExpectationsAnalyzer.compute(ds=review_ds, top_k=12, max_evidence_per_need=6)
                rating_opt = ReviewRatingOptimizationAnalyzer.compute(ds=review_ds, top_k_points=25, max_evidence_per_topic=5)

                for r in (result, sentiment, usage, motivation, expectations, rating_opt):
                    computed.append((r.output.module_code, r.output.model_dump(), int(r.output.schema_version), r.evidence_rows))

            if listing_ds is not None:
                market = MarketProductDetailsAnalyzer.compute(
                    ds=listing_ds,
                    target_asins=target_asins,
                    competitor_asins=competitor_asins,
                    max_evidence=120,
                )
                computed.append((market.output.module_code, market.output.model_dump(), int(market.output.schema_version), market.evidence_rows))

            if keyword_ds is not None:
                kwd = KeywordDetailsAnalyzer.compute(
                    ds=keyword_ds,
                    target_asins=target_asins,
                    top_items_per_keyword=8,
                    max_evidence_per_keyword=20,
                )
                computed.append((kwd.output.module_code, kwd.output.model_dump(), int(kwd.output.schema_version), kwd.evidence_rows))

            # ---------- persisting ----------
            last_stage = "persisting"
            await VocRepository.update_job_status(db, job_id=int(job_id), status=int(VocJobStatus.PERSISTING), stage=last_stage)
            await db.commit()

            for module_code, payload, schema_version, evidence_rows in computed:
                await _persist_module(module_code=module_code, output_payload=payload, schema_version=schema_version, evidence_rows=evidence_rows)

            await db.commit()

            # ---------- build report.v1 (reads outputs/evidence only) ----------
            report = await ReportV1Builder.build(db, job_id=int(job_id))
            await _persist_module(
                module_code=report.module_code,
                output_payload=report.model_dump(),
                schema_version=int(report.schema_version),
                evidence_rows=[],
            )
            await db.commit()

            # ---------- done ----------
            last_stage = "done"
            await VocRepository.update_job_status(db, job_id=int(job_id), status=int(VocJobStatus.DONE), stage=last_stage)
            await db.commit()

        except AppError:
            raise
        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass

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
