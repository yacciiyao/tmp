# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Review analyzer (MVP - overview metrics + evidence samples)

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from domains.voc_domain import Review, ReviewDataset
from domains.voc_output_domain import VocEvidenceItem, VocModuleOutput


def _day_from_epoch(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def _safe_snippet(text: str, max_len: int = 220) -> str:
    s = (text or "").replace("\r", " ").replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


@dataclass
class ReviewOverviewResult:
    output: VocModuleOutput
    evidence_rows: List[Dict[str, Any]]


class ReviewOverviewAnalyzer:
    """Compute basic review overview metrics.

    This is deterministic (no LLM). Designed as the first closed-loop module.
    """

    MODULE_CODE = "review.overview"
    SCHEMA_VERSION = 1

    @staticmethod
    def compute(*, ds: ReviewDataset, days_for_trend: int = 30) -> ReviewOverviewResult:
        reviews = list(ds.reviews or [])
        n = len(reviews)

        # ---------- rating stats ----------
        stars_sum = sum(int(r.stars) for r in reviews) if reviews else 0
        avg_stars = round(stars_sum / n, 4) if n > 0 else None

        dist = Counter(int(r.stars) for r in reviews)
        dist_rows = []
        for s in range(5, 0, -1):
            c = int(dist.get(s, 0))
            pct = round(c / n, 6) if n > 0 else 0
            dist_rows.append({"stars": s, "count": c, "pct": pct})

        # ---------- time trend ----------
        # Only include reviews that have review_time.
        by_day_cnt: Dict[str, int] = defaultdict(int)
        by_day_sum: Dict[str, int] = defaultdict(int)
        for r in reviews:
            if r.review_time is None:
                continue
            d = _day_from_epoch(int(r.review_time))
            by_day_cnt[d] += 1
            by_day_sum[d] += int(r.stars)

        # pick last N days ending today(UTC)
        today = datetime.now(tz=timezone.utc).date()
        days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_for_trend - 1, -1, -1)]
        trend_rows = []
        for d in days:
            c = int(by_day_cnt.get(d, 0))
            avg = round(by_day_sum[d] / c, 4) if c > 0 else None
            trend_rows.append({"day": d, "count": c, "avg_stars": avg})

        # ---------- evidence samples ----------
        neg = [r for r in reviews if int(r.stars) <= 2]
        pos = [r for r in reviews if int(r.stars) >= 4]

        def _sort_key(r: Review) -> Tuple[int, int, int]:
            # helpful desc, time desc, id desc
            return (int(r.helpful_votes or 0), int(r.review_time or 0), int(r.review_id))

        neg_sorted = sorted(neg, key=_sort_key, reverse=True)[:10]
        pos_sorted = sorted(pos, key=_sort_key, reverse=True)[:10]

        def _to_sample(r: Review) -> Dict[str, Any]:
            return {
                "review_id": int(r.review_id),
                "asin": r.asin,
                "stars": int(r.stars),
                "helpful_votes": int(r.helpful_votes or 0),
                "review_time": int(r.review_time) if r.review_time is not None else None,
                "title": r.review_title,
                "snippet": _safe_snippet(r.review_body or r.review_title or ""),
                "review_url": r.review_url,
                "verified_purchase": int(r.verified_purchase or 0),
            }

        neg_samples = [_to_sample(r) for r in neg_sorted]
        pos_samples = [_to_sample(r) for r in pos_sorted]

        # evidence rows for DB
        evidence_rows: List[Dict[str, Any]] = []
        for r in neg_sorted:
            evidence_rows.append(
                {
                    "source_type": "review",
                    "source_id": int(r.review_id),
                    "kind": "negative",
                    "snippet": _safe_snippet(r.review_body or r.review_title or ""),
                    "meta_json": {
                        "asin": r.asin,
                        "stars": int(r.stars),
                        "helpful_votes": int(r.helpful_votes or 0),
                        "review_time": int(r.review_time) if r.review_time is not None else None,
                        "review_url": r.review_url,
                    },
                }
            )
        for r in pos_sorted:
            evidence_rows.append(
                {
                    "source_type": "review",
                    "source_id": int(r.review_id),
                    "kind": "positive",
                    "snippet": _safe_snippet(r.review_body or r.review_title or ""),
                    "meta_json": {
                        "asin": r.asin,
                        "stars": int(r.stars),
                        "helpful_votes": int(r.helpful_votes or 0),
                        "review_time": int(r.review_time) if r.review_time is not None else None,
                        "review_url": r.review_url,
                    },
                }
            )

        out = VocModuleOutput(
            available=True,
            module_code=ReviewOverviewAnalyzer.MODULE_CODE,
            schema_version=ReviewOverviewAnalyzer.SCHEMA_VERSION,
            data={
                "summary": {
                    "review_count": n,
                    "avg_stars": avg_stars,
                },
                "rating_distribution": dist_rows,
                "trend_last_days": {
                    "days": days_for_trend,
                    "rows": trend_rows,
                },
                "evidence_samples": {
                    "negative": neg_samples,
                    "positive": pos_samples,
                },
            },
            meta={
                "site_code": ds.site_code,
                "asins": ds.asins,
                "review_time_from": ds.review_time_from,
                "review_time_to": ds.review_time_to,
            },
        )

        return ReviewOverviewResult(output=out, evidence_rows=evidence_rows)
