# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Amazon 运营助手工作流（LoadData -> Analyze -> Evidence/Compose -> ResultSchemaV1）

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple, Type

from sqlalchemy.ext.asyncio import AsyncSession

from domains.amazon_domain import (
    AmazonCompetitorMatrixReq,
    AmazonListingAuditReq,
    AmazonMarketResearchReq,
    AmazonOpportunityScanReq,
    AmazonProductImprovementReq,
    AmazonReviewVocReq,
    AmazonTaskKind,
)
from domains.common_result_domain import ResultSchemaV1, StepTrace, Trace, Meta
from domains.error_domain import AppError
from infrastructures.db.orm.analysis_job_orm import OpsAnalysisJobsORM
from infrastructures.vlogger import vlogger
from services.amazon.analyzers.aoa01_opportunity import analyze_aoa01
from services.amazon.analyzers.aoa02_market import analyze_aoa02
from services.amazon.analyzers.aoa03_competitor import analyze_aoa03
from services.amazon.analyzers.aoa04_listing import analyze_aoa04
from services.amazon.analyzers.aoa05_voc import analyze_aoa05
from services.amazon.analyzers.aoa06_improvement import analyze_aoa06
from infrastructures.db.repository.amazon_repository import AmazonRepository
from domains.spider_domain import SpiderTaskStatus
from services.common.result_evaluator import ResultEvaluator
from services.rag.rag_capability import RagCapability
from services.spider.spider_task_service import SpiderTaskService


AmazonReqType = (
    AmazonOpportunityScanReq
    | AmazonMarketResearchReq
    | AmazonCompetitorMatrixReq
    | AmazonListingAuditReq
    | AmazonReviewVocReq
    | AmazonProductImprovementReq
)


class AmazonWorkflow:
    """Amazon 工作流：读取爬虫 locator -> 拉取 MySQL 源数据 -> 分派 analyzer -> 生成 ResultSchemaV1"""

    def __init__(self) -> None:
        self._spider_svc = SpiderTaskService()
        self._repo = AmazonRepository()
        self._rag = RagCapability()

    async def run(self, db: AsyncSession, *, job: OpsAnalysisJobsORM) -> Dict[str, Any]:
        payload: Dict[str, Any] = dict(job.payload or {})
        task_kind = str(payload.get("task_kind") or "")
        if task_kind not in (
            AmazonTaskKind.AOA_01,
            AmazonTaskKind.AOA_02,
            AmazonTaskKind.AOA_03,
            AmazonTaskKind.AOA_04,
            AmazonTaskKind.AOA_05,
            AmazonTaskKind.AOA_06,
        ):
            raise AppError(
                code="amazon.invalid_task_kind",
                message="invalid task_kind",
                http_status=422,
                details={"task_kind": task_kind, "job_id": int(job.job_id)},
            )

        req_dict = payload.get("req") or {}
        req = self._parse_req(task_kind, req_dict)

        if not job.spider_task_id:
            raise AppError(
                code="amazon.missing_spider_task_id",
                message="job.spider_task_id is required",
                http_status=500,
                details={"job_id": int(job.job_id)},
            )

        steps: List[StepTrace] = []

        # 1) locator
        locator, st = await self._step_locator(db, job=job, request_id=req.request_id)
        steps.append(st)

        crawl_batch_no = int(locator["crawl_batch_no"])
        site = str(locator["site"])

        # 2) load data
        snapshots, reviews, keyword_metrics, st = await self._step_load_data(
            db,
            task_kind=task_kind,
            crawl_batch_no=crawl_batch_no,
            site=site,
            req=req,
        )
        steps.append(st)

        # 3) rag (可选)
        rag_hits: Optional[List[Dict[str, Any]]] = None
        if getattr(req, "use_rag", False):
            rag_hits, st = await self._step_rag(db, req=req, request_id=req.request_id)
            steps.append(st)

        # 4) analyze
        result_obj, st = await self._step_analyze(
            task_kind=task_kind,
            req=req,
            locator=locator,
            snapshots=snapshots,
            reviews=reviews,
            keyword_metrics=keyword_metrics,
            rag_hits=rag_hits,
        )
        steps.append(st)

        # 4.1) quality eval warnings（不改变 schema，不失败）
        eval_warnings = ResultEvaluator.evaluate(result_obj)
        if eval_warnings:
            result_obj.warnings.extend(eval_warnings)

        # 5) finalize trace/meta
        result_obj.trace = Trace(
            request_id=req.request_id,
            job_id=int(job.job_id),
            job_type=int(job.job_type),
            status=int(job.status),
            error_code=(str(job.error_code) if job.error_code else None),
            error_message=(str(job.error_message) if job.error_message else None),
            created_at=int(job.created_at),
            updated_at=int(job.updated_at),
            created_by=int(job.created_by),
            spider_task_id=int(job.spider_task_id),
            crawl_locator=dict(locator),
            task_kind=str(task_kind),
            biz="amazon",
            steps=steps,
        )
        result_obj.meta = Meta(
            schema_version="v1",
            ruleset_version="v1",
            operator_user_id=int(job.created_by),
        )
        result_obj.result_created_at = int(time.time())
        result_obj.result_updated_at = int(time.time())

        return result_obj.model_dump(mode="json")

    @staticmethod
    def _parse_req(task_kind: str, req_dict: Dict[str, Any]) -> AmazonReqType:
        mapping: Dict[str, Type[AmazonReqType]] = {
            AmazonTaskKind.AOA_01: AmazonOpportunityScanReq,
            AmazonTaskKind.AOA_02: AmazonMarketResearchReq,
            AmazonTaskKind.AOA_03: AmazonCompetitorMatrixReq,
            AmazonTaskKind.AOA_04: AmazonListingAuditReq,
            AmazonTaskKind.AOA_05: AmazonReviewVocReq,
            AmazonTaskKind.AOA_06: AmazonProductImprovementReq,
        }
        cls = mapping.get(task_kind)
        if cls is None:
            raise AppError(code="amazon.req_not_supported", message="req type not supported", http_status=500)
        return cls(**req_dict)

    async def _step_locator(
        self,
        db: AsyncSession,
        *,
        job: OpsAnalysisJobsORM,
        request_id: Optional[str],
    ) -> Tuple[Dict[str, Any], StepTrace]:
        start_ts = int(time.time())
        start = time.perf_counter()

        task_id = int(job.spider_task_id)
        task = await self._spider_svc.get_task(db, task_id=task_id)
        if not task:
            raise AppError(
                code="spider.task_not_found",
                message="spider_task not found",
                http_status=404,
                details={"spider_task_id": task_id, "job_id": int(job.job_id)},
            )

        # worker 只会处理 job.status=READY，但仍做一次强校验，保证不猜测、不兜底
        if int(task.status) == int(SpiderTaskStatus.FAILED.value):
            raise AppError(
                code=str(task.error_code or "spider.failed"),
                message=str(task.error_message or "spider task failed"),
                http_status=500,
                details={"spider_task_id": task_id, "job_id": int(job.job_id)},
            )
        if int(task.status) != int(SpiderTaskStatus.READY.value):
            raise AppError(
                code="spider.not_ready",
                message="spider task is not ready",
                http_status=409,
                details={"spider_task_id": task_id, "status": int(task.status), "job_id": int(job.job_id)},
            )

        locator = dict(task.result_locator or {})
        if "crawl_batch_no" not in locator or "site" not in locator:
            raise AppError(
                code="spider.invalid_locator",
                message="result_locator must include crawl_batch_no and site",
                http_status=500,
                details={"spider_task_id": task_id, "locator": locator},
            )

        dur_ms = int((time.perf_counter() - start) * 1000)
        st = StepTrace(
            step="locator",
            started_at=start_ts,
            finished_at=int(time.time()),
            duration_ms=dur_ms,
            note=f"spider_task_id={int(job.spider_task_id)} rid={request_id or '-'}",
        )
        return locator, st

    async def _step_load_data(
        self,
        db: AsyncSession,
        *,
        task_kind: str,
        crawl_batch_no: int,
        site: str,
        req: AmazonReqType,
    ) -> Tuple[List[Any], List[Any], List[Any], StepTrace]:
        start_ts = int(time.time())
        start = time.perf_counter()

        top_n = int(getattr(req.filters, "top_n", 50))
        asin = (req.query.asin or "").strip() if hasattr(req, "query") else ""
        category = (req.query.category or "").strip() if hasattr(req, "query") else ""

        snapshots: List[Any] = []
        reviews: List[Any] = []
        keyword_metrics: List[Any] = []

        # snapshots
        if task_kind in (AmazonTaskKind.AOA_04, AmazonTaskKind.AOA_06):
            # Listing 审计/产品改进：只需要目标 ASIN 快照
            snapshots = await self._repo.list_snapshots(
                db,
                crawl_batch_no=crawl_batch_no,
                site=site,
                limit=50,
                asins=[asin] if asin else None,
            )
        elif task_kind == AmazonTaskKind.AOA_03:
            # 竞品矩阵：需要目标 ASIN + 竞品候选集合（不能只读目标，否则无法对比）
            target_rows: List[Any] = []
            if asin:
                target_rows = await self._repo.list_snapshots(
                    db,
                    crawl_batch_no=crawl_batch_no,
                    site=site,
                    limit=5,
                    asins=[asin],
                )

            candidate_limit = max(80, min(500, max(2 * top_n, 200)))
            candidates = await self._repo.list_snapshots(
                db,
                crawl_batch_no=crawl_batch_no,
                site=site,
                limit=candidate_limit,
                category_contains=category or None,
                price_min=req.filters.price_min,
                price_max=req.filters.price_max,
            )

            # merge unique by asin (stable)
            by_asin: Dict[str, Any] = {}
            for r in target_rows + candidates:
                a = str(getattr(r, "asin", "") or "")
                if not a:
                    continue
                if a not in by_asin:
                    by_asin[a] = r
            snapshots = list(by_asin.values())
        else:
            snapshots = await self._repo.list_snapshots(
                db,
                crawl_batch_no=crawl_batch_no,
                site=site,
                limit=max(80, min(500, max(top_n, 80))),
                category_contains=category or None,
                price_min=req.filters.price_min,
                price_max=req.filters.price_max,
            )

        # reviews
        if task_kind in (AmazonTaskKind.AOA_05, AmazonTaskKind.AOA_06):
            review_limit = 2000 if top_n >= 50 else 1000
            reviews = await self._repo.list_reviews(
                db,
                crawl_batch_no=crawl_batch_no,
                site=site,
                limit=review_limit,
                asins=[asin] if asin else None,
            )
        elif task_kind == AmazonTaskKind.AOA_03:
            # 竞品矩阵：只取目标 ASIN 少量评论用于辅助判断（无需全量，避免拉太大）
            reviews = await self._repo.list_reviews(
                db,
                crawl_batch_no=crawl_batch_no,
                site=site,
                limit=500,
                asins=[asin] if asin else None,
            )

        # keyword_metrics
        keyword_metrics = await self._repo.list_keyword_metrics(
            db,
            crawl_batch_no=crawl_batch_no,
            site=site,
            limit=800,
        )

        dur_ms = int((time.perf_counter() - start) * 1000)
        st = StepTrace(
            step="load_data",
            started_at=start_ts,
            finished_at=int(time.time()),
            duration_ms=dur_ms,
            note=f"snapshots={len(snapshots)} reviews={len(reviews)} keywords={len(keyword_metrics)}",
        )
        return snapshots, reviews, keyword_metrics, st

    async def _step_rag(
        self,
        db: AsyncSession,
        *,
        req: AmazonReqType,
        request_id: Optional[str],
    ) -> Tuple[List[Dict[str, Any]], StepTrace]:
        start_ts = int(time.time())
        start = time.perf_counter()

        kb_space = str(req.kb_space or "").strip()
        query = (req.extra_notes or "").strip() or "amazon operation constraints"
        resp = await self._rag.search(db, kb_space=kb_space, query=query, top_k=8, request_id=request_id)
        hits: List[Dict[str, Any]] = []
        for h in resp.hits:
            hits.append(
                {
                    "kb_space": h.kb_space,
                    "document_id": h.document_id,
                    "chunk_id": h.chunk_id,
                    "score": h.score,
                    "content": h.content,
                }
            )

        dur_ms = int((time.perf_counter() - start) * 1000)
        st = StepTrace(
            step="rag",
            started_at=start_ts,
            finished_at=int(time.time()),
            duration_ms=dur_ms,
            note=f"hits={len(hits)}",
        )
        return hits, st

    async def _step_analyze(
        self,
        *,
        task_kind: str,
        req: AmazonReqType,
        locator: Dict[str, Any],
        snapshots: List[Any],
        reviews: List[Any],
        keyword_metrics: List[Any],
        rag_hits: Optional[List[Dict[str, Any]]],
    ) -> Tuple[ResultSchemaV1, StepTrace]:
        start_ts = int(time.time())
        start = time.perf_counter()

        if task_kind == AmazonTaskKind.AOA_01:
            result = analyze_aoa01(req=req, locator=locator, snapshots=snapshots, keyword_metrics=keyword_metrics, rag_hits=rag_hits)
        elif task_kind == AmazonTaskKind.AOA_02:
            result = analyze_aoa02(req=req, locator=locator, snapshots=snapshots, keyword_metrics=keyword_metrics, rag_hits=rag_hits)
        elif task_kind == AmazonTaskKind.AOA_03:
            result = analyze_aoa03(req=req, locator=locator, snapshots=snapshots, reviews=reviews, rag_hits=rag_hits)
        elif task_kind == AmazonTaskKind.AOA_04:
            result = analyze_aoa04(req=req, locator=locator, snapshots=snapshots, keyword_metrics=keyword_metrics, rag_hits=rag_hits)
        elif task_kind == AmazonTaskKind.AOA_05:
            result = analyze_aoa05(req=req, locator=locator, reviews=reviews, rag_hits=rag_hits)
        elif task_kind == AmazonTaskKind.AOA_06:
            result = analyze_aoa06(req=req, locator=locator, snapshots=snapshots, reviews=reviews, rag_hits=rag_hits)
        else:
            raise AppError(code="amazon.analyzer_not_found", message="analyzer not found", http_status=500)

        dur_ms = int((time.perf_counter() - start) * 1000)
        st = StepTrace(
            step="analyze",
            started_at=start_ts,
            finished_at=int(time.time()),
            duration_ms=dur_ms,
            note=f"task_kind={task_kind}",
        )
        vlogger.info("amazon.workflow analyzed task_kind=%s duration_ms=%s", task_kind, dur_ms)
        return result, st
