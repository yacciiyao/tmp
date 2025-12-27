# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Review buyers motivation analyzer (MVP - dictionary matching + evidence)

from __future__ import annotations

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
class ReviewBuyersMotivationResult:
    output: VocModuleOutput
    evidence_rows: List[Dict[str, Any]]


class ReviewBuyersMotivationAnalyzer:
    """Infer buyers' motivations from reviews.

    Deterministic MVP (no LLM): keyword dictionary matching.
    Each review may map to multiple motivations.
    """

    MODULE_CODE = "review.buyers_motivation"
    SCHEMA_VERSION = 1

    # Minimal motivation dictionary; can be expanded later or moved to config.
    # Key: motivation label; Value: list of lowercase keywords/phrases.
    DEFAULT_MOTIVATION_DICT: Dict[str, List[str]] = {
        "protection": ["protect", "protection", "keep safe", "safe", "secure"],
        "value_for_price": ["price", "value", "affordable", "cheap", "for the price"],
        "replacement": ["replace", "replacement", "replaced", "old one", "broke", "broken"],
        "gift": ["gift", "present", "christmas", "birthday"],
        "daily_carry": ["daily", "every day", "everyday", "commute", "commuting"],
        "organization": ["cable", "charger", "pocket", "pockets", "organize", "organization"],
    }

    @staticmethod
    def compute(
        *,
        ds: ReviewDataset,
        motivation_dict: Dict[str, List[str]] | None = None,
        top_k: int = 12,
        max_evidence_per_motivation: int = 6,
    ) -> ReviewBuyersMotivationResult:
        reviews = list(ds.reviews or [])
        total_n = len(reviews)

        if total_n == 0:
            out = VocModuleOutput(
                available=False,
                module_code=ReviewBuyersMotivationAnalyzer.MODULE_CODE,
                schema_version=ReviewBuyersMotivationAnalyzer.SCHEMA_VERSION,
                data={"unavailable_reason": "no_reviews"},
                meta={
                    "site_code": ds.site_code,
                    "asins": ds.asins,
                    "review_time_from": ds.review_time_from,
                    "review_time_to": ds.review_time_to,
                },
            )
            return ReviewBuyersMotivationResult(output=out, evidence_rows=[])

        mdict = motivation_dict or ReviewBuyersMotivationAnalyzer.DEFAULT_MOTIVATION_DICT

        matched: Dict[str, List[Review]] = defaultdict(list)
        for r in reviews:
            text = f"{r.review_title or ''} {r.review_body or ''}".lower()
            for motivation, keys in mdict.items():
                if not keys:
                    continue
                if any(k in text for k in keys if k):
                    matched[motivation].append(r)

        rows: List[Dict[str, Any]] = []
        evidence_rows: List[Dict[str, Any]] = []

        for motivation, rs in matched.items():
            uniq = {int(r.review_id): r for r in rs}.values()
            uniq_list = list(uniq)
            if not uniq_list:
                continue

            mention_count = len(uniq_list)
            pct = round(mention_count / total_n, 6) if total_n > 0 else 0
            avg_rating = round(sum(int(r.stars) for r in uniq_list) / mention_count, 4) if mention_count > 0 else None

            picked = sorted(uniq_list, key=_sort_key, reverse=True)[:max_evidence_per_motivation]
            snippets: List[str] = []
            for r in picked:
                snippet = _safe_snippet(r.review_body or r.review_title or "")
                snippets.append(snippet)
                evidence_rows.append(
                    {
                        "source_type": "review",
                        "source_id": int(r.review_id),
                        "kind": "motivation",
                        "snippet": snippet,
                        "meta_json": {
                            "motivation": motivation,
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
                    "motivation": motivation,
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
            module_code=ReviewBuyersMotivationAnalyzer.MODULE_CODE,
            schema_version=ReviewBuyersMotivationAnalyzer.SCHEMA_VERSION,
            data={"items": rows},
            meta={
                "site_code": ds.site_code,
                "asins": ds.asins,
                "review_time_from": ds.review_time_from,
                "review_time_to": ds.review_time_to,
            },
        )

        return ReviewBuyersMotivationResult(output=out, evidence_rows=evidence_rows)
