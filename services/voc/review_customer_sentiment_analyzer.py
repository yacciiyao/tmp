# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Review customer sentiment analyzer (MVP - deterministic topics + evidence)

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Set, Tuple

from domains.voc_domain import Review, ReviewDataset
from domains.voc_output_domain import VocModuleOutput


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


_STOPWORDS: Set[str] = {
    # Minimal English stopwords set for deterministic MVP.
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


def _tokenize(text: str) -> List[str]:
    tokens = [t.lower() for t in _TOKEN_RE.findall(text or "")]
    # filter
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
    """Map raw phrase to a stable topic key.

    MVP rule: simple heuristics + a tiny synonym mapping.
    """

    p = (phrase or "").lower().strip()
    if not p:
        return ""

    # Heuristic buckets
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

    # fallback: snake_case the phrase
    return p.replace(" ", "_")


def _sort_key(r: Review) -> Tuple[int, int, int]:
    return (int(r.helpful_votes or 0), int(r.review_time or 0), int(r.review_id))


@dataclass
class ReviewCustomerSentimentResult:
    output: VocModuleOutput
    evidence_rows: List[Dict[str, Any]]


class ReviewCustomerSentimentAnalyzer:
    """Extract customer sentiment topics from reviews.

    Deterministic MVP (no LLM):
    - Positive group: stars >= 4
    - Negative group: stars <= 2
    - Topics: top n-grams (2-3) + normalization heuristics
    """

    MODULE_CODE = "review.customer_sentiment"
    SCHEMA_VERSION = 1

    @staticmethod
    def compute(
        *,
        ds: ReviewDataset,
        top_k: int = 12,
        max_evidence_per_topic: int = 5,
    ) -> ReviewCustomerSentimentResult:
        reviews = list(ds.reviews or [])
        total_n = len(reviews)

        if total_n == 0:
            out = VocModuleOutput(
                available=False,
                module_code=ReviewCustomerSentimentAnalyzer.MODULE_CODE,
                schema_version=ReviewCustomerSentimentAnalyzer.SCHEMA_VERSION,
                data={"unavailable_reason": "no_reviews"},
                meta={
                    "site_code": ds.site_code,
                    "asins": ds.asins,
                    "review_time_from": ds.review_time_from,
                    "review_time_to": ds.review_time_to,
                },
            )
            return ReviewCustomerSentimentResult(output=out, evidence_rows=[])

        pos_reviews = [r for r in reviews if int(r.stars) >= 4]
        neg_reviews = [r for r in reviews if int(r.stars) <= 2]

        def _extract_topics(group: List[Review]) -> Tuple[List[Dict[str, Any]], Dict[str, List[Review]]]:
            # doc frequency of phrases
            phrase_df = Counter()
            phrase_to_reviews: Dict[str, Set[int]] = defaultdict(set)

            for r in group:
                text = f"{r.review_title or ''} {r.review_body or ''}".strip()
                tokens = _tokenize(text)
                # per-review unique phrases
                phrases: Set[str] = set()
                for n in (2, 3):
                    for p in _ngrams(tokens, n):
                        # filter noisy ngrams
                        if any(w in _STOPWORDS for w in p.split()):
                            continue
                        phrases.add(p)
                # fallback: if no ngrams, try a few unigrams
                if not phrases:
                    phrases.update(tokens[:20])
                for p in phrases:
                    phrase_df[p] += 1
                    phrase_to_reviews[p].add(int(r.review_id))

            # Map phrases -> topics, aggregate reviews by topic
            topic_to_review_ids: Dict[str, Set[int]] = defaultdict(set)
            for phrase, review_ids in phrase_to_reviews.items():
                topic = _normalize_topic(phrase)
                if not topic:
                    continue
                topic_to_review_ids[topic].update(review_ids)

            # Build topic rows
            topic_rows: List[Dict[str, Any]] = []
            topic_to_reviews: Dict[str, List[Review]] = defaultdict(list)
            # index reviews by id for quick lookup
            id_map = {int(r.review_id): r for r in group}

            for topic, ids in topic_to_review_ids.items():
                ids_list = [i for i in ids if i in id_map]
                if not ids_list:
                    continue
                rs = [id_map[i] for i in ids_list]
                topic_to_reviews[topic] = rs
                mention_count = len(ids_list)
                pct = round(mention_count / total_n, 6) if total_n > 0 else 0
                avg_rating = round(sum(int(r.stars) for r in rs) / mention_count, 4) if mention_count > 0 else None
                topic_rows.append(
                    {
                        "topic": topic,
                        "percentage": pct,
                        "mention_count": mention_count,
                        "avg_rating": avg_rating,
                    }
                )

            # Sort by mention_count desc then avg_rating (for positive higher, negative lower)
            topic_rows.sort(key=lambda x: (int(x.get("mention_count") or 0), float(x.get("avg_rating") or 0.0)), reverse=True)
            return topic_rows[:top_k], topic_to_reviews

        pos_topics, pos_topic_reviews = _extract_topics(pos_reviews)
        neg_topics, neg_topic_reviews = _extract_topics(neg_reviews)

        # Build evidence rows and reasons
        evidence_rows: List[Dict[str, Any]] = []

        def _attach_reason_and_evidence(
            rows: List[Dict[str, Any]],
            topic_reviews: Dict[str, List[Review]],
            kind: str,
        ) -> List[Dict[str, Any]]:
            out_rows: List[Dict[str, Any]] = []
            for row in rows:
                topic = str(row["topic"])
                rs = sorted(topic_reviews.get(topic, []), key=_sort_key, reverse=True)
                rs = rs[:max_evidence_per_topic]
                snippets = []
                for r in rs:
                    snippet = _safe_snippet(r.review_body or r.review_title or "")
                    snippets.append(snippet)
                    evidence_rows.append(
                        {
                            "source_type": "review",
                            "source_id": int(r.review_id),
                            "kind": kind,
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
                reason = " ".join(snippets[:2]).strip() if snippets else None
                new_row = dict(row)
                new_row["reason"] = reason
                out_rows.append(new_row)
            return out_rows

        pos_topics = _attach_reason_and_evidence(pos_topics, pos_topic_reviews, kind="positive_topic")
        neg_topics = _attach_reason_and_evidence(neg_topics, neg_topic_reviews, kind="negative_topic")

        out = VocModuleOutput(
            available=True,
            module_code=ReviewCustomerSentimentAnalyzer.MODULE_CODE,
            schema_version=ReviewCustomerSentimentAnalyzer.SCHEMA_VERSION,
            data={
                "positive_topics": pos_topics,
                "negative_topics": neg_topics,
            },
            meta={
                "site_code": ds.site_code,
                "asins": ds.asins,
                "review_time_from": ds.review_time_from,
                "review_time_to": ds.review_time_to,
            },
        )

        return ReviewCustomerSentimentResult(output=out, evidence_rows=evidence_rows)
