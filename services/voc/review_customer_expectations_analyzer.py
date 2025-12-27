# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Review customer expectations analyzer (MVP - unmet needs extraction + evidence)

from __future__ import annotations

import re
from collections import Counter, defaultdict
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


_EXPECT_PATTERNS = [
    re.compile(r"\bexpected\b", re.IGNORECASE),
    re.compile(r"\bexpecting\b", re.IGNORECASE),
    re.compile(r"\bwish\b", re.IGNORECASE),
    re.compile(r"\bhoped\b", re.IGNORECASE),
    re.compile(r"\bhope\b", re.IGNORECASE),
    re.compile(r"\bshould\b", re.IGNORECASE),
    re.compile(r"\bcould\b", re.IGNORECASE),
    re.compile(r"\bwould be better\b", re.IGNORECASE),
    re.compile(r"\bneeds to\b", re.IGNORECASE),
]


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


def _normalize_need(phrase: str) -> str:
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
    if "quality" in p:
        return "quality"
    if "smell" in p or "odor" in p:
        return "odor"
    if "pocket" in p or "pockets" in p:
        return "more_pockets"
    if "thick" in p or "thicker" in p:
        return "thicker_padding"
    if "soft" in p or "lining" in p:
        return "soft_lining"

    return p.replace(" ", "_")


def _sentences(text: str) -> List[str]:
    # lightweight sentence split
    raw = (text or "").replace("\r", " ").replace("\n", " ")
    parts = re.split(r"[\.!?]+", raw)
    return [p.strip() for p in parts if p and p.strip()]


@dataclass
class ReviewCustomerExpectationsResult:
    output: VocModuleOutput
    evidence_rows: List[Dict[str, Any]]


class ReviewCustomerExpectationsAnalyzer:
    """Extract unmet customer expectations from reviews.

    Deterministic MVP:
    - Focus on reviews with stars <= 3 (more likely to contain unmet expectations)
    - Find sentences containing expectation markers (expected/wish/should/could...)
    - Extract n-grams from these sentences and normalize into need keys
    """

    MODULE_CODE = "review.customer_expectations"
    SCHEMA_VERSION = 1

    @staticmethod
    def compute(
        *,
        ds: ReviewDataset,
        top_k: int = 12,
        max_evidence_per_need: int = 6,
    ) -> ReviewCustomerExpectationsResult:
        reviews = list(ds.reviews or [])
        total_n = len(reviews)

        if total_n == 0:
            out = VocModuleOutput(
                available=False,
                module_code=ReviewCustomerExpectationsAnalyzer.MODULE_CODE,
                schema_version=ReviewCustomerExpectationsAnalyzer.SCHEMA_VERSION,
                data={"unavailable_reason": "no_reviews"},
                meta={
                    "site_code": ds.site_code,
                    "asins": ds.asins,
                    "review_time_from": ds.review_time_from,
                    "review_time_to": ds.review_time_to,
                },
            )
            return ReviewCustomerExpectationsResult(output=out, evidence_rows=[])

        # Candidate pool: <=3 stars (neutral and negative)
        candidates = [r for r in reviews if int(r.stars) <= 3]
        if not candidates:
            out = VocModuleOutput(
                available=True,
                module_code=ReviewCustomerExpectationsAnalyzer.MODULE_CODE,
                schema_version=ReviewCustomerExpectationsAnalyzer.SCHEMA_VERSION,
                data={"items": []},
                meta={
                    "site_code": ds.site_code,
                    "asins": ds.asins,
                    "review_time_from": ds.review_time_from,
                    "review_time_to": ds.review_time_to,
                },
            )
            return ReviewCustomerExpectationsResult(output=out, evidence_rows=[])

        # need -> set(review_id)
        need_to_review_ids: Dict[str, Set[int]] = defaultdict(set)
        review_id_to_need_hits: Dict[int, Set[str]] = defaultdict(set)

        for r in candidates:
            text = f"{r.review_title or ''}. {r.review_body or ''}".strip()
            for sent in _sentences(text):
                if not any(p.search(sent) for p in _EXPECT_PATTERNS):
                    continue
                tokens = _tokenize(sent)
                phrases: Set[str] = set()
                for n in (2, 3):
                    for p in _ngrams(tokens, n):
                        if any(w in _STOPWORDS for w in p.split()):
                            continue
                        phrases.add(p)
                if not phrases:
                    phrases.update(tokens[:15])
                for ph in phrases:
                    need = _normalize_need(ph)
                    if not need:
                        continue
                    need_to_review_ids[need].add(int(r.review_id))
                    review_id_to_need_hits[int(r.review_id)].add(need)

        if not need_to_review_ids:
            out = VocModuleOutput(
                available=True,
                module_code=ReviewCustomerExpectationsAnalyzer.MODULE_CODE,
                schema_version=ReviewCustomerExpectationsAnalyzer.SCHEMA_VERSION,
                data={"items": []},
                meta={
                    "site_code": ds.site_code,
                    "asins": ds.asins,
                    "review_time_from": ds.review_time_from,
                    "review_time_to": ds.review_time_to,
                },
            )
            return ReviewCustomerExpectationsResult(output=out, evidence_rows=[])

        # build need rows
        id_map = {int(r.review_id): r for r in candidates}
        rows: List[Dict[str, Any]] = []
        evidence_rows: List[Dict[str, Any]] = []

        for need, ids in need_to_review_ids.items():
            ids_list = [i for i in ids if i in id_map]
            if not ids_list:
                continue
            rs = [id_map[i] for i in ids_list]
            mention_count = len(ids_list)
            pct = round(mention_count / total_n, 6) if total_n > 0 else 0
            avg_rating = round(sum(int(r.stars) for r in rs) / mention_count, 4) if mention_count > 0 else None

            picked = sorted(rs, key=_sort_key, reverse=True)[:max_evidence_per_need]
            snippets: List[str] = []
            for r in picked:
                snippet = _safe_snippet(r.review_body or r.review_title or "")
                snippets.append(snippet)
                evidence_rows.append(
                    {
                        "source_type": "review",
                        "source_id": int(r.review_id),
                        "kind": "expectation",
                        "snippet": snippet,
                        "meta_json": {
                            "unmet_need": need,
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
                    "unmet_need": need,
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
            module_code=ReviewCustomerExpectationsAnalyzer.MODULE_CODE,
            schema_version=ReviewCustomerExpectationsAnalyzer.SCHEMA_VERSION,
            data={"items": rows},
            meta={
                "site_code": ds.site_code,
                "asins": ds.asins,
                "review_time_from": ds.review_time_from,
                "review_time_to": ds.review_time_to,
            },
        )

        return ReviewCustomerExpectationsResult(output=out, evidence_rows=evidence_rows)
