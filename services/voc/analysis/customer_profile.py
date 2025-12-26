# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Customer Profile analyzer (Who/When/Where/What) with fixed labels.

from __future__ import annotations

import heapq
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Pattern, Tuple


@dataclass(frozen=True)
class ReviewLite:
    """Minimal review fields needed for evidence and profile matching."""

    review_item_id: int
    stars: int
    review_time: Optional[int]
    review_title: Optional[str]
    review_body: str
    helpful_votes: Optional[int]
    is_verified_purchase: Optional[bool]
    options_text: Optional[str]

    @property
    def text(self) -> str:
        title = (self.review_title or "").strip()
        body = (self.review_body or "").strip()
        return f"{title}\n{body}".strip()


def _compile_pattern(pattern: str) -> Pattern[str]:
    return re.compile(pattern, flags=re.IGNORECASE)


def default_profile_patterns() -> Dict[str, List[Tuple[str, Pattern[str]]]]:
    """Fixed label buckets for Customer Profile.

    Output format:
        {
          "who": [("son", compiled_pattern), ...],
          "when": [...],
          "where": [...],
          "what": [...],
        }

    Notes:
        - Terms are intentionally fixed (per product category UI).
        - Patterns are *not* a fixed topic taxonomy; only used for profile buckets.
    """

    who = [
        ("son", _compile_pattern(r"\bson\b")),
        ("daughter", _compile_pattern(r"\bdaughter(s)?\b")),
        ("wife", _compile_pattern(r"\bwife\b")),
        ("husband", _compile_pattern(r"\bhusband\b")),
        ("kid", _compile_pattern(r"\bkids?\b")),
        ("child", _compile_pattern(r"\bchild(ren)?\b")),
        ("boy", _compile_pattern(r"\bboy(s)?\b")),
        ("girl", _compile_pattern(r"\bgirl(s)?\b")),
        ("teen", _compile_pattern(r"\bteen(ager)?s?\b")),
        ("friend", _compile_pattern(r"\bfriend(s)?\b")),
        ("family", _compile_pattern(r"\bfamily\b")),
    ]

    when = [
        ("everyday", _compile_pattern(r"\bevery\s*day\b|\beveryday\b")),
        ("christmas", _compile_pattern(r"\bchristmas\b")),
        ("night", _compile_pattern(r"\bnight(s)?\b")),
        ("morning", _compile_pattern(r"\bmorn(ing)?s?\b")),
        ("weekend", _compile_pattern(r"\bweekend(s)?\b")),
        ("travel", _compile_pattern(r"\btravel(ing)?\b|\btrip(s)?\b|\bvacation\b")),
        ("school", _compile_pattern(r"\bschool\b|\bclass\b")),
        ("work", _compile_pattern(r"\bwork\b|\boffice\b|\bcommute\b")),
    ]

    where = [
        ("gym", _compile_pattern(r"\bgym\b")),
        ("pocket", _compile_pattern(r"\bpocket(s)?\b")),
        ("car", _compile_pattern(r"\bcar\b|\bdriv(e|ing)\b")),
        ("house", _compile_pattern(r"\bhome\b|\bhouse\b")),
        ("plane", _compile_pattern(r"\bplane\b|\bflight\b|\bairplane\b")),
        ("office", _compile_pattern(r"\boffice\b")),
        ("school", _compile_pattern(r"\bschool\b")),
    ]

    what = [
        ("workout", _compile_pattern(r"\bwork\s*out\b|\bworkout\b|\bexercise\b|\btraining\b")),
        ("gift", _compile_pattern(r"\bgift\b|\bpresent\b|\bbought\s+for\b")),
        ("run", _compile_pattern(r"\brun(ning)?\b|\bjog(ging)?\b")),
        ("phone", _compile_pattern(r"\bphone\b|\bcall(s)?\b|\bzoom\b|\bmeeting\b")),
        ("music", _compile_pattern(r"\bmusic\b|\blisten(ing)?\b")),
        ("travel", _compile_pattern(r"\btravel\b|\bcommute\b|\btrip\b")),
    ]

    return {"who": who, "when": when, "where": where, "what": what}


def _score_tuple(r: ReviewLite) -> Tuple[int, int, int]:
    """Higher is better."""
    hv = int(r.helpful_votes or 0)
    tl = len(r.review_body or "")
    rt = int(r.review_time or 0)
    return hv, tl, rt


class _TopK:
    def __init__(self, k: int):
        self.k = int(k)
        self._heap: List[Tuple[Tuple[int, int, int], int, ReviewLite]] = []
        self._seq = 0

    def consider(self, r: ReviewLite) -> None:
        key = _score_tuple(r)
        self._seq += 1
        entry = (key, self._seq, r)
        if len(self._heap) < self.k:
            heapq.heappush(self._heap, entry)
            return
        if entry[0] > self._heap[0][0]:
            heapq.heapreplace(self._heap, entry)

    def items_desc(self) -> List[ReviewLite]:
        return [x[2] for x in sorted(self._heap, key=lambda t: t[0], reverse=True)]


@dataclass
class ProfileStats:
    total_reviews: int
    mentions: Dict[str, Dict[str, int]]  # axis -> term -> count
    evidence: Dict[str, Dict[str, List[ReviewLite]]]  # axis -> term -> topK reviews
    top_terms: Dict[str, Optional[str]]  # axis -> best term


class ProfileAccumulator:
    """Streaming accumulator for Customer Profile.

    Use this when reviews are read in batches from DB.
    """

    def __init__(
        self,
        *,
        patterns: Optional[Dict[str, List[Tuple[str, Pattern[str]]]]] = None,
        evidence_per_term: int = 8,
    ) -> None:
        self.patterns = patterns or default_profile_patterns()
        self.axes = ["who", "when", "where", "what"]
        self.mentions: Dict[str, Dict[str, int]] = {a: {t: 0 for t, _ in self.patterns[a]} for a in self.axes}
        self._topk: Dict[str, Dict[str, _TopK]] = {
            a: {t: _TopK(evidence_per_term) for t, _ in self.patterns[a]} for a in self.axes
        }

    def add(self, r: ReviewLite) -> None:
        text = r.text
        if not text:
            return
        for axis in self.axes:
            for term, pat in self.patterns[axis]:
                if pat.search(text) is None:
                    continue
                self.mentions[axis][term] += 1
                self._topk[axis][term].consider(r)

    def finalize(self, *, total_reviews: int) -> ProfileStats:
        evidence: Dict[str, Dict[str, List[ReviewLite]]] = {
            a: {t: self._topk[a][t].items_desc() for t, _ in self.patterns[a]} for a in self.axes
        }
        top_terms: Dict[str, Optional[str]] = {}
        for axis in self.axes:
            best_term = None
            best_cnt = -1
            for term, _ in self.patterns[axis]:
                cnt = int(self.mentions[axis][term])
                if cnt > best_cnt:
                    best_cnt = cnt
                    best_term = term
            top_terms[axis] = best_term if best_cnt > 0 else None
        return ProfileStats(
            total_reviews=int(total_reviews),
            mentions=self.mentions,
            evidence=evidence,
            top_terms=top_terms,
        )


def analyze_customer_profile(
    reviews: Iterable[ReviewLite],
    *,
    total_reviews: int,
    patterns: Optional[Dict[str, List[Tuple[str, Pattern[str]]]]] = None,
    evidence_per_term: int = 8,
) -> ProfileStats:
    """Analyze Customer Profile (Who/When/Where/What).

    Metrics are computed on *all* reviews. Evidence keeps only a small representative subset.
    """
    patterns = patterns or default_profile_patterns()
    axes = ["who", "when", "where", "what"]

    mentions: Dict[str, Dict[str, int]] = {a: {t: 0 for t, _ in patterns[a]} for a in axes}
    topk: Dict[str, Dict[str, _TopK]] = {a: {t: _TopK(evidence_per_term) for t, _ in patterns[a]} for a in axes}

    for r in reviews:
        text = r.text
        if not text:
            continue

        # Per review, count each term at most once.
        for axis in axes:
            for term, pat in patterns[axis]:
                if pat.search(text) is None:
                    continue
                mentions[axis][term] += 1
                topk[axis][term].consider(r)

    evidence: Dict[str, Dict[str, List[ReviewLite]]] = {
        a: {t: topk[a][t].items_desc() for t, _ in patterns[a]} for a in axes
    }
    top_terms: Dict[str, Optional[str]] = {}
    for axis in axes:
        best_term = None
        best_cnt = -1
        for term, _ in patterns[axis]:
            cnt = int(mentions[axis][term])
            if cnt > best_cnt:
                best_cnt = cnt
                best_term = term
        top_terms[axis] = best_term if best_cnt > 0 else None

    return ProfileStats(
        total_reviews=int(total_reviews),
        mentions=mentions,
        evidence=evidence,
        top_terms=top_terms,
    )
