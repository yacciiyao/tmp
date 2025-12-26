# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC domain (job/task level contracts, task-agnostic)

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field

from domains.domain_base import DomainModel


class VocJobType(str, Enum):
    """Job types supported by VOC.

    Keep this enum task-agnostic. Specific task payloads/reports live in
    their own domain modules (e.g. voc_review_domain).
    """

    REVIEW_ANALYSIS = "review_analysis"


class VocCreateReviewAnalysisJobRequest(DomainModel):
    """User input: site_code + asin (no hidden params)."""

    site_code: str = Field(..., min_length=2, max_length=16, description="站点代码，如 US")
    asin: str = Field(..., min_length=6, max_length=32, description="Amazon ASIN")


class VocCreateJobResponse(DomainModel):
    """Create job response contract (v1)."""

    job_id: int
    status: int
    report_id: Optional[int] = None


class VocJobResponse(DomainModel):
    """Job row projection for API."""

    job_id: int
    job_type: str
    site_code: str
    asin: Optional[str] = None
    keyword: Optional[str] = None
    category: Optional[str] = None

    status: int
    try_count: int
    max_retries: int
    locked_by: Optional[str] = None
    locked_until: Optional[int] = None
    report_id: Optional[int] = None
    last_error: Optional[str] = None

    created_at: int
    updated_at: int


class VocSpiderCallbackRequest(DomainModel):
    """Spider callback request.

    - status: READY | FAILED | RUNNING (case-insensitive)
    - run_id: results SSOT run_id when READY
    - callback_token: one-time token per task (plain text), validated by sha256 in app_db
    """

    task_id: str = Field(..., min_length=6, max_length=128)
    status: str = Field(..., min_length=3, max_length=16)
    run_id: Optional[int] = Field(default=None, ge=1)
    error: Optional[str] = Field(default=None, max_length=2000)
    callback_token: str = Field(..., min_length=16, max_length=256)


class VocSpiderCallbackResponse(DomainModel):
    updated_task_rows: int
    updated_job_rows: int
