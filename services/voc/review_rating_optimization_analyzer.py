# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Review rating optimization analyzer (MVP - topic scatter + evidence)

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Set, Tuple

from domains.voc_domain import Review, ReviewDataset
from domains.voc_output_domain import VocModuleOutput


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

_STOPWORDS: Set[str] = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "me",
    "my",
    "not",
    "of",
    "on",
    "or",
    "our",
    "so",
    "that",
    "the",
    "their",
    "this",
    "to",
    "too",
    "was",
    "we",
    "were",
    "with",
    "you",
    "your",
}


def _safe_snippet(text: str, max_len: int = 220) -> str:
    s = (text or "").replace("\r", " ").replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def _sort_key(r: Review) -> Tuple[int, int, int]:
    return (int(r.helpful_votes or 0), int(r.review_time or 0), int(r.review_id))


def _tokenize(text: str) -> List[str]:
    tokens = [t.lower() for t in _TOKEN_RE.findall(text or "")]
    out: List[str] = []
    for t in tokens:
        if len(t) <= 2:
            continue
        if t in _STOPWORDS:
            continue
        out.append(t)
    return out


def _ngrams(tokens: List[str], n: int) -> Iterable[str]:
    if len(tokens) < n:
        return []
    return (" ".join(tokens[i : i + n]) for i in range(0, len(tokens) - n + 1))


def _normalize_topic(phrase: str) -> str:
    p = (phrase or "").lower().strip()
    if not p:
        return ""

    if "water" in p and ("resist" in p or "proof" in p):
        return "water_resistance"
    if "zip" in p or "zipper" in p:
        return "zipper"
    if "stitch" in p or "seam" in p or "sew" in p:
        return "stitching"
    if "pad" in p or "cushion" in p or "padding" in p:
        return "padding"
    if "fit" in p or "size" in p:
        return "fit"
    if "price" in p or "value" in p:
        return "value"
    if "soft" in p or "lining" in p:
        return "soft_lining"
    if "smell" in p or "odor" in p:
        return "odor"
    if "quality" in p:
        return "quality"
    if "protect" in p or "protection" in p:
        return "protection"

    return p.replace(" ", "_")


@dataclass
class ReviewRatingOptimizationResult:
    output: VocModuleOutput
    evidence_rows: List[Dict[str, Any]]


class ReviewRatingOptimizationAnalyzer:
    """Build rating-optimization scatter points based on topic mentions.

    Deterministic MVP:
    - Extract topics from n-grams (2-3) over all reviews
    - Normalize topics with heuristics
    - For each topic: mentions (#reviews) and avg_rating
    - Evidence focuses on the most-mentioned low-rating topics
    """

    MODULE_CODE = "review.rating_optimization"
    SCHEMA_VERSION = 1

    @staticmethod
    def compute(
        *,
        ds: ReviewDataset,
        top_k_points: int = 25,
        max_evidence_per_topic: int = 5,
        low_rating_threshold: float = 3.5,
    ) -> ReviewRatingOptimizationResult:
        reviews = list(ds.reviews or [])
        total_n = len(reviews)

        if total_n == 0:
            out = VocModuleOutput(
                available=False,
                module_code=ReviewRatingOptimizationAnalyzer.MODULE_CODE,
                schema_version=ReviewRatingOptimizationAnalyzer.SCHEMA_VERSION,
                data={"unavailable_reason": "no_reviews"},
                meta={
                    "site_code": ds.site_code,
                    "asins": ds.asins,
                    "review_time_from": ds.review_time_from,
                    "review_time_to": ds.review_time_to,
                },
            )
            return ReviewRatingOptimizationResult(output=out, evidence_rows=[])

        # topic -> set(review_id)
        topic_to_ids: Dict[str, Set[int]] = defaultdict(set)
        # index
        id_map = {int(r.review_id): r for r in reviews}

        for r in reviews:
            text = f"{r.review_title or ''} {r.review_body or ''}".strip()
            tokens = _tokenize(text)
            phrases: Set[str] = set()
            for n in (2, 3):
                for p in _ngrams(tokens, n):
                    if any(w in _STOPWORDS for w in p.split()):
                        continue
                    phrases.add(p)
            if not phrases:
                phrases.update(tokens[:20])
            for ph in phrases:
                topic = _normalize_topic(ph)
                if topic:
                    topic_to_ids[topic].add(int(r.review_id))

        points: List[Dict[str, Any]] = []
        for topic, ids in topic_to_ids.items():
            ids_list = [i for i in ids if i in id_map]
            if not ids_list:
                continue
            rs = [id_map[i] for i in ids_list]
            mentions = len(ids_list)
            avg_rating = round(sum(int(r.stars) for r in rs) / mentions, 4) if mentions > 0 else None
            points.append(
                {
                    "topic": topic,
                    "mentions": mentions,
                    "avg_rating": avg_rating,
                }
            )

        # sort points by mentions desc
        points.sort(key=lambda x: (int(x.get("mentions") or 0), -float(x.get("avg_rating") or 0.0)), reverse=True)
        points = points[:top_k_points]

        # evidence for low-rating topics among top points
        evidence_rows: List[Dict[str, Any]] = []
        actionable = [p for p in points if p.get("avg_rating") is not None and float(p["avg_rating"]) <= low_rating_threshold]
        # prioritize by mentions
        actionable.sort(key=lambda x: int(x.get("mentions") or 0), reverse=True)
        actionable = actionable[:8]

        for p in actionable:
            topic = str(p["topic"])
            ids = list(topic_to_ids.get(topic, []))
            rs = [id_map[i] for i in ids if i in id_map]
            rs = sorted(rs, key=_sort_key, reverse=True)[:max_evidence_per_topic]
            for r in rs:
                snippet = _safe_snippet(r.review_body or r.review_title or "")
                evidence_rows.append(
                    {
                        "source_type": "review",
                        "source_id": int(r.review_id),
                        "kind": "rating_opt_topic",
                        "snippet": snippet,
                        "meta_json": {
                            "topic": topic,
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
            module_code=ReviewRatingOptimizationAnalyzer.MODULE_CODE,
            schema_version=ReviewRatingOptimizationAnalyzer.SCHEMA_VERSION,
            data={
                "points": points,
                "low_rating_threshold": low_rating_threshold,
            },
            meta={
                "site_code": ds.site_code,
                "asins": ds.asins,
                "review_time_from": ds.review_time_from,
                "review_time_to": ds.review_time_to,
            },
        )

        return ReviewRatingOptimizationResult(output=out, evidence_rows=evidence_rows)
