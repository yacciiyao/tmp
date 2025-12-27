# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Review usage scenario analyzer (MVP - dictionary matching + evidence)

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from domains.voc_domain import Review, ReviewDataset
from domains.voc_output_domain import VocModuleOutput


def _safe_snippet(text: str, max_len: int = 220) -> str:
    s = (text or "").replace("\r", " ").replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def _sort_key(r: Review) -> Tuple[int, int, int]:
    # helpful desc, time desc, id desc
    return (int(r.helpful_votes or 0), int(r.review_time or 0), int(r.review_id))


@dataclass
class ReviewUsageScenarioResult:
    output: VocModuleOutput
    evidence_rows: List[Dict[str, Any]]


class ReviewUsageScenarioAnalyzer:
    """Infer usage scenarios from reviews.

    Deterministic MVP (no LLM): keyword dictionary matching.
    - Each review may map to multiple scenarios.
    - Scenario metrics are computed over all reviews in the dataset.
    """

    MODULE_CODE = "review.usage_scenario"
    SCHEMA_VERSION = 1

    # Minimal scenario dictionary; can be expanded later or moved to config.
    # Key: scenario label; Value: list of lowercase keywords/phrases.
    DEFAULT_SCENARIO_DICT: Dict[str, List[str]] = {
        "travel": ["travel", "plane", "airport", "flight", "vacation", "trip", "hotel"],
        "commuting": ["commute", "commuting", "train", "subway", "bus", "metro"],
        "school": ["school", "class", "college", "campus", "student", "backpack"],
        "office": ["office", "work", "workplace", "desk"],
        "gym": ["gym", "workout", "fitness"],
        "gift": ["gift", "present", "christmas", "birthday"],
    }

    @staticmethod
    def compute(
        *,
        ds: ReviewDataset,
        scenario_dict: Dict[str, List[str]] | None = None,
        top_k: int = 12,
        max_evidence_per_scenario: int = 6,
    ) -> ReviewUsageScenarioResult:
        reviews = list(ds.reviews or [])
        total_n = len(reviews)

        if total_n == 0:
            out = VocModuleOutput(
                available=False,
                module_code=ReviewUsageScenarioAnalyzer.MODULE_CODE,
                schema_version=ReviewUsageScenarioAnalyzer.SCHEMA_VERSION,
                data={"unavailable_reason": "no_reviews"},
                meta={
                    "site_code": ds.site_code,
                    "asins": ds.asins,
                    "review_time_from": ds.review_time_from,
                    "review_time_to": ds.review_time_to,
                },
            )
            return ReviewUsageScenarioResult(output=out, evidence_rows=[])

        sdict = scenario_dict or ReviewUsageScenarioAnalyzer.DEFAULT_SCENARIO_DICT

        # scenario -> list[Review]
        matched: Dict[str, List[Review]] = defaultdict(list)

        for r in reviews:
            text = f"{r.review_title or ''} {r.review_body or ''}".lower()
            for scenario, keys in sdict.items():
                if not keys:
                    continue
                # simple substring match
                if any(k in text for k in keys if k):
                    matched[scenario].append(r)

        # Build rows
        rows: List[Dict[str, Any]] = []
        evidence_rows: List[Dict[str, Any]] = []

        for scenario, rs in matched.items():
            # de-dup by review_id
            uniq = {int(r.review_id): r for r in rs}.values()
            uniq_list = list(uniq)
            if not uniq_list:
                continue
            mention_count = len(uniq_list)
            pct = round(mention_count / total_n, 6) if total_n > 0 else 0
            avg_rating = round(sum(int(r.stars) for r in uniq_list) / mention_count, 4) if mention_count > 0 else None

            # evidence
            picked = sorted(uniq_list, key=_sort_key, reverse=True)[:max_evidence_per_scenario]
            snippets = []
            for r in picked:
                snippet = _safe_snippet(r.review_body or r.review_title or "")
                snippets.append(snippet)
                evidence_rows.append(
                    {
                        "source_type": "review",
                        "source_id": int(r.review_id),
                        "kind": "scenario",
                        "snippet": snippet,
                        "meta_json": {
                            "scenario": scenario,
                            "asin": r.asin,
                            "stars": int(r.stars),
                            "helpful_votes": int(r.helpful_votes or 0),
                            "review_time": int(r.review_time) if r.review_time is not None else None,
                            "review_url": r.review_url,
                        },
                    }
                )

            reason = " ".join(snippets[:2]).strip() if snippets else None

            rows.append(
                {
                    "scenario": scenario,
                    "percentage": pct,
                    "mention_count": mention_count,
                    "avg_rating": avg_rating,
                    "reason": reason,
                }
            )

        rows.sort(key=lambda x: (float(x.get("percentage") or 0.0), int(x.get("mention_count") or 0)), reverse=True)
        rows = rows[:top_k]

        out = VocModuleOutput(
            available=True,
            module_code=ReviewUsageScenarioAnalyzer.MODULE_CODE,
            schema_version=ReviewUsageScenarioAnalyzer.SCHEMA_VERSION,
            data={"items": rows},
            meta={
                "site_code": ds.site_code,
                "asins": ds.asins,
                "review_time_from": ds.review_time_from,
                "review_time_to": ds.review_time_to,
            },
        )

        return ReviewUsageScenarioResult(output=out, evidence_rows=evidence_rows)
