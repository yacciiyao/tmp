# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: ORM mappings for spider(results) DB tables used by VOC.
#
# IMPORTANT:
#   - This file mirrors /mnt/data/results.sql (read-only schema).
#   - Do NOT run migrations/DDL against spider DB from this project.

from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String, Text, Numeric
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from infrastructures.db.spider_orm.spider_orm_base import SpiderBase


# -----------------------------
# Spider meta tables
# -----------------------------


class SpiderTasksORM(SpiderBase):
    __tablename__ = "spider_tasks"

    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)
    caller: Mapped[str] = mapped_column(String(32), nullable=False)
    caller_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)

    site_code: Mapped[str] = mapped_column(String(8), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_value: Mapped[str] = mapped_column(String(256), nullable=False)

    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finished_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)

    stats_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    callback_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    callback_method: Mapped[str] = mapped_column(String(8), nullable=False, default="POST")
    callback_headers_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    callback_body_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    callback_status: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    callback_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    callback_last_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    callback_next_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    callback_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    callback_error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class SpiderRunsORM(SpiderBase):
    __tablename__ = "spider_runs"

    run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    run_type: Mapped[str] = mapped_column(String(32), nullable=False)
    page_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    request_url: Mapped[str] = mapped_column(Text, nullable=False)
    request_method: Mapped[str] = mapped_column(String(8), nullable=False, default="GET")
    request_headers_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finished_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

    results_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    mongo_doc_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)


# -----------------------------
# Amazon reviews
# -----------------------------


class AmazonReviewItemsORM(SpiderBase):
    __tablename__ = "amazon_review_items"

    review_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    site_code: Mapped[str] = mapped_column(String(8), nullable=False)
    asin: Mapped[str] = mapped_column(String(16), nullable=False)

    review_external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    item_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    stars: Mapped[int] = mapped_column(Integer, nullable=False)
    review_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reviewer_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_time: Mapped[int | None] = mapped_column(Integer, nullable=True)

    helpful_votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verified_purchase: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    options_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)


class AmazonReviewMediaORM(SpiderBase):
    __tablename__ = "amazon_review_media"

    media_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    review_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    media_type: Mapped[str] = mapped_column(String(16), nullable=False)
    media_url: Mapped[str] = mapped_column(Text, nullable=False)
    thumb_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)


class AmazonReviewObservationsORM(SpiderBase):
    __tablename__ = "amazon_review_observations"

    obs_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    run_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    site_code: Mapped[str] = mapped_column(String(8), nullable=False)
    asin: Mapped[str] = mapped_column(String(16), nullable=False)
    review_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    page_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    observed_at: Mapped[int] = mapped_column(Integer, nullable=False)


class AmazonReviewOptionsORM(SpiderBase):
    __tablename__ = "amazon_review_options"

    option_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    review_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    option_name: Mapped[str] = mapped_column(String(64), nullable=False)
    option_value: Mapped[str] = mapped_column(String(128), nullable=False)


# -----------------------------
# Amazon listing snapshots
# -----------------------------


class AmazonListingItemsORM(SpiderBase):
    __tablename__ = "amazon_listing_items"

    listing_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    run_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    captured_at: Mapped[int] = mapped_column(Integer, nullable=False)

    site_code: Mapped[str] = mapped_column(String(8), nullable=False)
    asin: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_asin: Mapped[str | None] = mapped_column(String(16), nullable=True)

    brand_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    about_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_information_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    main_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    price_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    stars: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    ratings_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    bought_past_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    availability_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    variation_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_path: Mapped[str | None] = mapped_column(String(512), nullable=True)


class AmazonListingAttributesORM(SpiderBase):
    __tablename__ = "amazon_listing_attributes"

    attr_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    attr_name: Mapped[str] = mapped_column(String(64), nullable=False)
    attr_value: Mapped[str] = mapped_column(String(255), nullable=False)


class AmazonListingBulletsORM(SpiderBase):
    __tablename__ = "amazon_listing_bullets"

    bullet_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    bullet_index: Mapped[int] = mapped_column(Integer, nullable=False)
    bullet_text: Mapped[str] = mapped_column(Text, nullable=False)


class AmazonListingMediaORM(SpiderBase):
    __tablename__ = "amazon_listing_media"

    media_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    media_type: Mapped[str] = mapped_column(String(16), nullable=False)
    media_url: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# -----------------------------
# Amazon keyword SERP
# -----------------------------


class AmazonKeywordSearchItemsORM(SpiderBase):
    __tablename__ = "amazon_keyword_search_items"

    kw_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    run_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    captured_at: Mapped[int] = mapped_column(Integer, nullable=False)

    site_code: Mapped[str] = mapped_column(String(8), nullable=False)
    keyword: Mapped[str] = mapped_column(String(256), nullable=False)

    page_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_sponsored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    asin: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    price_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    stars: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    ratings_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bought_past_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
