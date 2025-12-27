# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC domain data structures (datasets & entities).

from __future__ import annotations

from enum import IntEnum
from typing import Any, Dict, List, Optional

from pydantic import Field

from domains.domain_base import DomainModel, now_ts


# -----------------------------
# VOC job meta
# -----------------------------


class VocJobStatus(IntEnum):
    """VOC job state machine (frozen by spec)."""

    PENDING = 10
    CRAWLING = 20
    EXTRACTING = 30
    ANALYZING = 40
    PERSISTING = 50
    DONE = 60
    FAILED = 90


class VocJob(DomainModel):
    job_id: int
    input_hash: str
    status: int = int(VocJobStatus.PENDING)
    params_json: Dict[str, Any] = Field(default_factory=dict)

    preferred_task_id: Optional[int] = None
    preferred_run_id: Optional[int] = None

    error_code: Optional[str] = None
    error_message: Optional[str] = None
    failed_stage: Optional[str] = None

    created_at: int = Field(default_factory=now_ts)
    updated_at: int = Field(default_factory=now_ts)


# -----------------------------
# Results-side domain entities
# -----------------------------


class ReviewOption(DomainModel):
    option_name: str
    option_value: str


class ReviewMedia(DomainModel):
    media_type: str  # image/video
    media_url: str
    thumb_url: Optional[str] = None
    created_at: Optional[int] = None


class Review(DomainModel):
    review_id: int
    site_code: str
    asin: str

    review_external_id: Optional[str] = None
    item_fingerprint: str

    stars: int
    review_title: Optional[str] = None
    review_body: Optional[str] = None

    language_code: Optional[str] = None
    reviewer_name: Optional[str] = None
    review_location: Optional[str] = None
    review_time: Optional[int] = None

    helpful_votes: int = 0
    verified_purchase: int = 0

    options_text: Optional[str] = None
    review_url: Optional[str] = None

    created_at: Optional[int] = None
    updated_at: Optional[int] = None

    options: List[ReviewOption] = Field(default_factory=list)
    media: List[ReviewMedia] = Field(default_factory=list)


class ListingAttribute(DomainModel):
    attr_name: str
    attr_value: str


class ListingBullet(DomainModel):
    bullet_index: int
    bullet_text: str


class ListingMedia(DomainModel):
    media_type: str
    media_url: str
    position: int = 0


class ListingSnapshot(DomainModel):
    listing_id: int
    task_id: int
    run_id: int
    captured_at: int
    captured_day: Optional[str] = None  # derived in repository (YYYY-MM-DD)

    site_code: str
    asin: str
    parent_asin: Optional[str] = None

    brand_name: Optional[str] = None
    title: Optional[str] = None
    about_text: Optional[str] = None
    product_information_text: Optional[str] = None

    main_image_url: Optional[str] = None

    price_amount: Optional[float] = None
    price_currency: Optional[str] = None

    stars: Optional[float] = None
    ratings_count: Optional[int] = None
    review_count: Optional[int] = None
    bought_past_month: Optional[int] = None

    availability_text: Optional[str] = None
    seller_name: Optional[str] = None
    variation_summary: Optional[str] = None
    category_path: Optional[str] = None

    attributes: List[ListingAttribute] = Field(default_factory=list)
    bullets: List[ListingBullet] = Field(default_factory=list)
    media: List[ListingMedia] = Field(default_factory=list)


class SerpItem(DomainModel):
    kw_item_id: int
    task_id: int
    run_id: int
    captured_at: int
    captured_day: Optional[str] = None  # derived in repository (YYYY-MM-DD)

    site_code: str
    keyword: str
    page_num: int
    position: int
    is_sponsored: int = 0

    asin: str
    title: Optional[str] = None
    brand_name: Optional[str] = None
    image_url: Optional[str] = None
    product_url: Optional[str] = None

    price_amount: Optional[float] = None
    price_currency: Optional[str] = None

    stars: Optional[float] = None
    ratings_count: Optional[int] = None
    review_count: Optional[int] = None
    bought_past_month: Optional[int] = None


# -----------------------------
# Dataset wrappers (for services)
# -----------------------------


class ReviewDataset(DomainModel):
    site_code: str
    asins: List[str]
    review_time_from: Optional[int] = None
    review_time_to: Optional[int] = None
    reviews: List[Review] = Field(default_factory=list)


class ListingDataset(DomainModel):
    site_code: str
    asins: List[str]
    start_day: Optional[str] = None
    end_day: Optional[str] = None
    snapshots: List[ListingSnapshot] = Field(default_factory=list)


class KeywordSerpDataset(DomainModel):
    site_code: str
    keywords: List[str]
    start_day: Optional[str] = None
    end_day: Optional[str] = None
    items: List[SerpItem] = Field(default_factory=list)
