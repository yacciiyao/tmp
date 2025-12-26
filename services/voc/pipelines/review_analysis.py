# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC review analysis pipeline (v1: skeleton)

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from domains.rag_domain import JobResultStatus, JobStatus
from domains.voc_review_domain import TermStatRow, ReviewEvidence, CustomerInsights, CustomerProfileSection, \
    UsageScenarioSection, RatingOptimizationSection, CustomerSentimentSection, BuyersMotivationSection, \
    CustomerExpectationsSection, ReviewAnalysisReport, EvidencePack

from infrastructures.db.repository.repository_base import now_ts
from infrastructures.db.repository.spider_results_repository import SpiderResultsRepository
from infrastructures.db.repository.voc_repository import VocRepository, VocSpiderTaskStatus
from infrastructures.db.spider_orm.spider_orm_base import SpiderAsyncSessionFactory
from infrastructures.vlogger import vlogger
from services.voc.analysis.customer_profile import default_profile_patterns, ReviewLite, ProfileAccumulator


@dataclass
class VocJobRunResult:
    job_id: int
    status: JobResultStatus
    message: str = ""
    report_id: Optional[int] = None
    data: Optional[dict[str, Any]] = None


def _truncate(s: str, n: int = 200) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 3].rstrip() + "..."


class ReviewAnalysisPipeline:
    """VOC Review Analysis pipeline.

    v1 goal:
        - Close the loop after spider callback: READY(run_id) -> analysis -> report -> job SUCCEEDED
        - Keep analysis logic minimal; focus on system wiring.
    """

    def __init__(
        self,
        *,
        repo: VocRepository,
        db_factory: Callable[[], AsyncSession],
        spider_repo: SpiderResultsRepository,
        spider_db_factory: Callable[[], AsyncSession] = SpiderAsyncSessionFactory,
    ) -> None:
        self.repo = repo
        self.db_factory = db_factory
        self.spider_repo = spider_repo
        self.spider_db_factory = spider_db_factory

    async def run_job(self, *, job_id: int, worker_id: str) -> VocJobRunResult:
        """Run a single VOC job.

        The pipeline itself is responsible for:
            - validating job/task state
            - reading spider results
            - creating ops_voc_reports
            - marking job status
        """
        async with self.db_factory() as db:
            job = await self.repo.get_job(db, job_id=int(job_id))
            if job is None:
                return VocJobRunResult(job_id=int(job_id), status=JobResultStatus.SUCCEEDED, message="job not found")

            # Safety: only the lock owner should run it.
            if int(job.status) == int(JobStatus.RUNNING):
                locked_by = str(job.locked_by or "")
                if locked_by and locked_by != str(worker_id):
                    return VocJobRunResult(
                        job_id=int(job.job_id),
                        status=JobResultStatus.SUCCEEDED,
                        message="job locked by other worker",
                        data={"locked_by": locked_by},
                    )

            try:
                tasks = await self.repo.list_spider_tasks_by_job(db, job_id=int(job.job_id))
                task = None
                for t in tasks:
                    # v1: one job -> one amazon_review task
                    if str(t.run_type) == "amazon_review":
                        task = t
                        break
                if task is None:
                    await self.repo.finish_job(
                        db,
                        job_id=int(job.job_id),
                        status=int(JobStatus.FAILED),
                        last_error="spider task missing",
                        clear_lock=True,
                    )
                    await db.commit()
                    return VocJobRunResult(job_id=int(job.job_id), status=JobResultStatus.FAILED, message="task missing")

                if int(task.status) != int(VocSpiderTaskStatus.READY) or task.run_id is None:
                    # Shouldn't happen due to claim_next_job guard, but keep it robust.
                    await self.repo.finish_job(
                        db,
                        job_id=int(job.job_id),
                        status=int(JobStatus.FAILED),
                        last_error="spider task not ready",
                        clear_lock=True,
                    )
                    await db.commit()
                    return VocJobRunResult(
                        job_id=int(job.job_id),
                        status=JobResultStatus.RETRYABLE,
                        message="spider task not ready",
                        data={"task_status": int(task.status), "run_id": task.run_id},
                    )

                run_id = int(task.run_id)

                # ---- Read spider(results) DB and compute metrics on ALL reviews ----
                evidence_per_term_heap = 8
                evidence_ids_per_term_row = 3
                global_evidence_topk = 30

                patterns = default_profile_patterns()
                acc = ProfileAccumulator(patterns=patterns, evidence_per_term=evidence_per_term_heap)

                # Keep a global evidence sample (top helpful votes) as generic proof/debugging.
                global_heap: List[tuple[tuple[int, int, int], int, ReviewLite]] = []
                global_seq = 0

                def consider_global(r: ReviewLite) -> None:
                    nonlocal global_seq
                    hv = int(r.helpful_votes or 0)
                    tl = len(r.review_body or "")
                    rt = int(r.review_time or 0)
                    key = (hv, tl, rt)
                    global_seq += 1
                    entry = (key, global_seq, r)
                    if len(global_heap) < global_evidence_topk:
                        import heapq

                        heapq.heappush(global_heap, entry)
                        return
                    if entry[0] > global_heap[0][0]:
                        import heapq

                        heapq.heapreplace(global_heap, entry)

                async with self.spider_db_factory() as sdb:
                    run = await self.spider_repo.get_run(sdb, run_id=run_id)
                    total = await self.spider_repo.count_reviews_by_run(sdb, run_id=run_id)

                    async for batch in self.spider_repo.iter_reviews_by_run(sdb, run_id=run_id, batch_size=1000):
                        for r in batch:
                            # normalize minimal fields
                            stars = int(r.stars or 0)
                            if stars < 1:
                                stars = 1
                            if stars > 5:
                                stars = 5
                            lite = ReviewLite(
                                review_item_id=int(r.item_id),
                                stars=stars,
                                review_time=int(r.review_time) if r.review_time is not None else None,
                                review_title=str(r.review_title) if r.review_title is not None else None,
                                review_body=str(r.review_body or ""),
                                helpful_votes=int(r.helpful_votes) if r.helpful_votes is not None else None,
                                is_verified_purchase=bool(r.is_verified_purchase) if r.is_verified_purchase is not None else None,
                                options_text=str(r.options_text) if r.options_text is not None else None,
                            )
                            acc.add(lite)
                            consider_global(lite)

                profile = acc.finalize(total_reviews=int(total))

                # ---- Build Customer Profile rows (fixed label order) ----
                def make_term_rows(axis: str) -> List[TermStatRow]:
                    rows: List[TermStatRow] = []
                    denom = float(profile.total_reviews) if profile.total_reviews > 0 else 0.0
                    for term, _pat in patterns[axis]:
                        m = int(profile.mentions[axis].get(term, 0))
                        pct = float(m) / denom if denom > 0 else 0.0
                        ev = profile.evidence[axis].get(term, [])[:evidence_ids_per_term_row]
                        rows.append(
                            TermStatRow(
                                term=str(term),
                                mentions=m,
                                percentage=pct,
                                evidence_ids=[f"review:{int(x.review_item_id)}" for x in ev],
                            )
                        )
                    return rows

                who_rows = make_term_rows("who")
                when_rows = make_term_rows("when")
                where_rows = make_term_rows("where")
                what_rows = make_term_rows("what")

                top_who = profile.top_terms.get("who")
                top_when = profile.top_terms.get("when")
                top_where = profile.top_terms.get("where")
                top_what = profile.top_terms.get("what")

                if top_who and top_when and top_where and top_what:
                    profile_summary = (
                        f'The consumer group most commonly mentioned is {top_who}, '
                        f'the most common moment of use is {top_when}, '
                        f'the most common location is {top_where}, '
                        f'the most common behavior is {top_what}.'
                    )
                else:
                    profile_summary = "Not enough explicit Who/When/Where/What signals found in reviews to summarize."

                # Pick a top term for examples (prefer Who)
                top_axis = None
                top_term = None
                if top_who:
                    top_axis, top_term = "who", top_who
                elif top_when:
                    top_axis, top_term = "when", top_when
                elif top_where:
                    top_axis, top_term = "where", top_where
                elif top_what:
                    top_axis, top_term = "what", top_what

                top_examples: List[str] = []
                if top_axis and top_term:
                    top_examples = [
                        f"review:{int(x.review_item_id)}"
                        for x in profile.evidence[top_axis].get(top_term, [])[:evidence_ids_per_term_row]
                    ]

                # ---- Evidence selection: union of row evidences + small global sample ----
                evidence_map: dict[int, ReviewLite] = {}
                for axis in ("who", "when", "where", "what"):
                    for term, _ in patterns[axis]:
                        for x in profile.evidence[axis].get(term, [])[:evidence_ids_per_term_row]:
                            evidence_map[int(x.review_item_id)] = x

                # add global sample
                for x in [t[2] for t in sorted(global_heap, key=lambda z: z[0], reverse=True)]:
                    if len(evidence_map) >= 120:
                        break
                    evidence_map.setdefault(int(x.review_item_id), x)

                evidence_reviews: List[ReviewEvidence] = []
                for x in sorted(evidence_map.values(), key=lambda r: (int(r.helpful_votes or 0), len(r.review_body)), reverse=True):
                    evidence_reviews.append(
                        ReviewEvidence(
                            evidence_id=f"review:{int(x.review_item_id)}",
                            review_item_id=int(x.review_item_id),
                            stars=int(x.stars),
                            review_time=int(x.review_time) if x.review_time is not None else None,
                            title=str(x.review_title) if x.review_title is not None else None,
                            body_excerpt=_truncate(str(x.review_body or ""), 240),
                            helpful_votes=int(x.helpful_votes) if x.helpful_votes is not None else None,
                            verified_purchase=bool(x.is_verified_purchase) if x.is_verified_purchase is not None else None,
                            options_text=str(x.options_text) if x.options_text is not None else None,
                            media_ids=[],
                        )
                    )

                customer_insights = CustomerInsights(
                    customer_profile=CustomerProfileSection(
                        summary=profile_summary,
                        who=who_rows,
                        when=when_rows,
                        where=where_rows,
                        what=what_rows,
                        top_term=(str(top_axis), str(top_term)) if top_axis and top_term else None,
                        top_term_examples=top_examples,
                    ),
                    usage_scenario=UsageScenarioSection(summary=None, rows=[]),
                    rating_optimization=RatingOptimizationSection(summary=None, scatter=[], top_drivers=[]),
                    customer_sentiment=CustomerSentimentSection(summary=None, negative=[], positive=[]),
                    buyers_motivation=BuyersMotivationSection(summary=None, rows=[]),
                    customer_expectations=CustomerExpectationsSection(summary=None, rows=[]),
                )

                report = ReviewAnalysisReport(
                    site_code=str(job.site_code),
                    asin=str(job.asin or ""),
                    run_id=int(run_id),
                    customer_insights=customer_insights,
                    evidence=EvidencePack(reviews=evidence_reviews, media=[]),
                )

                meta = {
                    "generated_at": now_ts(),
                    "worker_id": str(worker_id),
                    "run_id": int(run_id),
                    "review_total": int(total),
                    "evidence_review_count": int(len(evidence_reviews)),
                    "evidence_policy": {
                        "per_term_heap": int(evidence_per_term_heap),
                        "per_term_row": int(evidence_ids_per_term_row),
                        "global_sample": int(global_evidence_topk),
                        "total_cap": 120,
                    },
                    "analysis_version": "v1_profile_only",
                    "spider_source": str(getattr(run, "source", "")) if run is not None else "",
                    "spider_run_type": str(getattr(run, "run_type", "")) if run is not None else "",
                }

                # Persist report + mark job succeeded
                report_row = await self.repo.create_report(
                    db,
                    job_id=int(job.job_id),
                    report_type=str(job.job_type),
                    payload_json=report.model_dump(),
                    meta_json=meta,
                )

                await self.repo.finish_job(
                    db,
                    job_id=int(job.job_id),
                    status=int(JobStatus.SUCCEEDED),
                    last_error=None,
                    report_id=int(report_row.report_id),
                    clear_lock=True,
                )
                await db.commit()

                vlogger.info(
                    "voc report generated",
                    extra={
                        "job_id": int(job.job_id),
                        "report_id": int(report_row.report_id),
                        "run_id": int(run_id),
                        "review_total": int(total),
                    },
                )

                return VocJobRunResult(
                    job_id=int(job.job_id),
                    status=JobResultStatus.SUCCEEDED,
                    message="ok",
                    report_id=int(report_row.report_id),
                    data={"review_total": int(total)},
                )

            except Exception as e:
                # If any DB operation failed (e.g. flush/commit), the session may be in a pending rollback state.
                # Ensure we can safely issue follow-up UPDATEs to mark the job FAILED.
                try:
                    await db.rollback()
                except Exception:
                    pass
                # Best-effort: mark failed and clear lock so it can retry.
                err = str(e)[:2000]
                await self.repo.finish_job(
                    db,
                    job_id=int(job.job_id),
                    status=int(JobStatus.FAILED),
                    last_error=err,
                    clear_lock=True,
                )
                await db.commit()
                vlogger.exception("voc pipeline failed", extra={"job_id": int(job.job_id), "error": err})
                return VocJobRunResult(job_id=int(job.job_id), status=JobResultStatus.RETRYABLE, message=err)
