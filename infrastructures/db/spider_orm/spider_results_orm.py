# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: ORM mappings for spider(results) DB tables used by VOC.

from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from infrastructures.db.spider_orm.spider_orm_base import SpiderBase


class SpiderRunsORM(SpiderBase):
    __tablename__ = "spider_runs"

    run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    run_type: Mapped[str] = mapped_column(String(64), nullable=False)
    site: Mapped[str | None] = mapped_column(String(8), nullable=True)
    request_url: Mapped[str] = mapped_column(Text, nullable=False)
    request_method: Mapped[str | None] = mapped_column(String(8), nullable=True)
    request_body_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    results_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mongo_doc_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    captured_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scope_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    extra_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class AmazonReviewItemsORM(SpiderBase):
    __tablename__ = "amazon_review_items"

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    site: Mapped[str] = mapped_column(String(8), nullable=False)
    asin: Mapped[str] = mapped_column(String(16), nullable=False)
    page_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    review_external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    review_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    stars: Mapped[int] = mapped_column(Integer, nullable=False)
    is_verified_purchase: Mapped[int | None] = mapped_column(Integer, nullable=True)

    review_date_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    review_location: Mapped[str | None] = mapped_column(String(128), nullable=True)

    options_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    options_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    review_body: Mapped[str] = mapped_column(Text, nullable=False)
    helpful_votes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    helpful_votes_text: Mapped[str | None] = mapped_column(String(64), nullable=True)

    has_media: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    item_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    extra_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class AmazonReviewMediaORM(SpiderBase):
    __tablename__ = "amazon_review_media"

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    review_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    media_external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_type: Mapped[str] = mapped_column(String(16), nullable=False)
    media_url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
