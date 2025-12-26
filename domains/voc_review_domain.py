# -*- coding: utf-8 -*-
# @File: voc_review_domain.py
# @Author: yaccii
# @Time: 2025-12-26 18:54
# @Description:
# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC review analysis domain (report + analysis I/O)

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple

from pydantic import Field

from domains.domain_base import DomainModel


# -----------------------------
# Basic enums (review-specific)
# -----------------------------


class SentimentPolarity(str, Enum):
    NEGATIVE = "Negative"
    POSITIVE = "Positive"


# -----------------------------
# Evidence
# -----------------------------


class ReviewEvidence(DomainModel):
    """Evidence is the audit trail.

    Every row in report references evidence_ids that point here.

    evidence_id format: "review:{review_item_id}"
    """

    evidence_id: str
    review_item_id: int

    stars: int = Field(..., ge=1, le=5)
    review_time: Optional[int] = None  # epoch seconds if available
    title: Optional[str] = None
    body_excerpt: str  # deterministic short excerpt
    helpful_votes: Optional[int] = None
    verified_purchase: Optional[bool] = None
    options_text: Optional[str] = None  # e.g. "Color=Blue|Size=13 inch"

    media_ids: List[str] = Field(default_factory=list)  # ["media:123", ...]


class MediaEvidence(DomainModel):
    """Media evidence bound to a review evidence id.

    media_id format: "media:{review_media_id}" or "media:{review_item_id}:{idx}" if no id.
    Vision caption/tags are optional and can be filled later when enable_vision=True.
    """

    media_id: str
    review_evidence_id: str  # "review:{review_item_id}"

    url: str
    media_type: str = "image"  # "image" | "video" (v1 keep simple)
    caption: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class EvidencePack(DomainModel):
    reviews: List[ReviewEvidence] = Field(default_factory=list)
    media: List[MediaEvidence] = Field(default_factory=list)


# -----------------------------
# Common rows
# -----------------------------


class TermStatRow(DomainModel):
    """Used by Customer Profile (Who/When/Where/What)."""

    term: str
    mentions: int
    percentage: float  # mentions / total_reviews
    evidence_ids: List[str] = Field(default_factory=list)


class ScenarioRow(DomainModel):
    """Usage Scenario table row."""

    usage_scenario: str
    mentions: int
    percentage: float
    reason: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)


class TopicRow(DomainModel):
    """Customer Sentiment table row."""

    polarity: SentimentPolarity
    topic_key: str
    label_human: Optional[str] = None
    mentions: int
    percentage: float
    reason: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)

    phrases: List[str] = Field(default_factory=list)


class RatingScatterPoint(DomainModel):
    """Scatter for Rating Optimization: x=rating y=mentions."""

    topic_key: str
    rating: int = Field(..., ge=1, le=5)
    mentions: int


class RatingDriverRow(DomainModel):
    """A ranked list for "what to fix to lift rating"."""

    topic_key: str
    label_human: Optional[str] = None
    lift_potential: float
    evidence_ids: List[str] = Field(default_factory=list)


class MotivationRow(DomainModel):
    motivation_key: str
    label_human: Optional[str] = None
    mentions: int
    percentage: float
    reason: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)


class UnmetNeedRow(DomainModel):
    unmet_need_key: str
    label_human: Optional[str] = None
    mentions: int
    percentage: float
    reason: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)


# -----------------------------
# Sections (6 submodules)
# -----------------------------


class CustomerProfileSection(DomainModel):
    summary: Optional[str] = None

    who: List[TermStatRow] = Field(default_factory=list)
    when: List[TermStatRow] = Field(default_factory=list)
    where: List[TermStatRow] = Field(default_factory=list)
    what: List[TermStatRow] = Field(default_factory=list)

    top_term: Optional[Tuple[str, str]] = None  # (axis, term)
    top_term_examples: List[str] = Field(default_factory=list)


class UsageScenarioSection(DomainModel):
    summary: Optional[str] = None
    rows: List[ScenarioRow] = Field(default_factory=list)


class RatingOptimizationSection(DomainModel):
    summary: Optional[str] = None
    scatter: List[RatingScatterPoint] = Field(default_factory=list)
    top_drivers: List[RatingDriverRow] = Field(default_factory=list)


class CustomerSentimentSection(DomainModel):
    summary: Optional[str] = None
    negative: List[TopicRow] = Field(default_factory=list)
    positive: List[TopicRow] = Field(default_factory=list)


class BuyersMotivationSection(DomainModel):
    summary: Optional[str] = None
    rows: List[MotivationRow] = Field(default_factory=list)


class CustomerExpectationsSection(DomainModel):
    summary: Optional[str] = None
    rows: List[UnmetNeedRow] = Field(default_factory=list)


class CustomerInsights(DomainModel):
    customer_profile: CustomerProfileSection
    usage_scenario: UsageScenarioSection
    rating_optimization: RatingOptimizationSection
    customer_sentiment: CustomerSentimentSection
    buyers_motivation: BuyersMotivationSection
    customer_expectations: CustomerExpectationsSection


# -----------------------------
# Pipeline I/O (internal)
# -----------------------------


class ReviewRawItem(DomainModel):
    """Minimal review row used by pipeline (from results SSOT)."""

    review_item_id: int
    stars: int
    review_time: Optional[int] = None
    title: Optional[str] = None
    body: str
    helpful_votes: Optional[int] = None
    verified_purchase: Optional[bool] = None
    options_text: Optional[str] = None


class ReviewRawMedia(DomainModel):
    review_media_id: Optional[int] = None
    review_item_id: int
    url: str
    media_type: str = "image"


class ReviewAnalysisInput(DomainModel):
    """Pipeline input, fully determined by a single run_id."""

    site_code: str
    asin: str
    run_id: int

    items: List[ReviewRawItem]
    media: List[ReviewRawMedia] = Field(default_factory=list)


class ReviewAnalysisReport(DomainModel):
    """Report payload (typed). Stored as JSON in DB."""

    site_code: str
    asin: str
    run_id: int

    customer_insights: CustomerInsights
    evidence: EvidencePack
