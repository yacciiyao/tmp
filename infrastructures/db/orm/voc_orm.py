# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC module ORM (service DB, NOT spider results DB)

from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from infrastructures.db.orm.orm_base import Base, TimestampMixin


class MetaVocJobsORM(Base, TimestampMixin):
    """VOC job table (one job per user request / batch).

    Stable columns:
      - input_hash: dedup key for idempotency (caller+scope+params normalized hash)
      - preferred_task_id/run_id: optional pointers to spider side (if job is triggered by AI crawl)
    """

    __tablename__ = "meta_voc_jobs"

    job_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    site_code: Mapped[str] = mapped_column(String(8), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="asin/keyword/brand/url/...")
    scope_value: Mapped[str] = mapped_column(String(256), nullable=False, comment="ASIN/keyword/...")

    params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    status: Mapped[int] = mapped_column(Integer, nullable=False, default=10, comment="VocJobStatus.*")
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="crawling/extracting/analyzing/persisting")

    preferred_task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    preferred_run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("input_hash", name="uk_voc_job_input_hash"),
        Index("idx_voc_job_scope_time", "site_code", "scope_type", "scope_value", "created_at"),
        Index("idx_voc_job_status_time", "status", "created_at"),
    )


class StgVocOutputsORM(Base, TimestampMixin):
    """VOC module output snapshots.

    This table is intentionally generic:
      - each module writes its own payload_json
      - payload_json must be forward compatible (fields are additive)
    """

    __tablename__ = "stg_voc_outputs"

    output_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    job_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    module_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="e.g. review.customer_profile")

    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("job_id", "module_code", name="uk_voc_output_job_module"),
        Index("idx_voc_output_job", "job_id"),
    )


class StgVocEvidenceORM(Base, TimestampMixin):
    """VOC evidence table.

    Evidence is the bridge between a computed conclusion and raw spider(results) records.

    - source_type: review/listing/serp
    - source_id: the primary key of the source table (e.g. review_id)
    - snippet: short text shown in UI
    - meta_json: extra structured info (stars/helpful_votes/asin/keyword/...)
    """

    __tablename__ = "stg_voc_evidence"

    evidence_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    job_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    module_code: Mapped[str] = mapped_column(String(64), nullable=False)

    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="pos/neg/neutral/...", default=None)

    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("idx_voc_evidence_job", "job_id"),
        Index("idx_voc_evidence_job_module", "job_id", "module_code"),
        Index("idx_voc_evidence_source", "source_type", "source_id"),
    )
