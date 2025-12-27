# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC job/request/output domain models.

from __future__ import annotations

from enum import IntEnum, Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from domains.domain_base import DomainModel, now_ts


class VocJobStatus(IntEnum):
    PENDING = 10
    CRAWLING = 20
    EXTRACTING = 30
    ANALYZING = 40
    PERSISTING = 50
    DONE = 60
    FAILED = 90


class VocJobStage(str, Enum):
    crawling = "crawling"
    extracting = "extracting"
    analyzing = "analyzing"
    persisting = "persisting"


class VocScopeType(str, Enum):
    voc = "voc"  # batch params in params_json


class VocTimeWindow(DomainModel):
    reviews_days: int = 365
    listing_days: int = 30
    serp_days: int = 30


class CreateVocJobRequest(DomainModel):
    site_code: str
    language: Optional[str] = None

    target_asins: List[str] = Field(default_factory=list)
    competitor_asins: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)

    time_window: VocTimeWindow = Field(default_factory=VocTimeWindow)
    trigger_mode: str = "AUTO"  # AUTO|FORCE|OFF


class CreateVocJobResponse(DomainModel):
    job_id: int
    status: int


class VocJobInfo(DomainModel):
    job_id: int
    status: int
    stage: Optional[str] = None

    site_code: str
    scope_type: str
    scope_value: str
    params_json: Dict[str, Any]

    preferred_task_id: Optional[int] = None
    preferred_run_id: Optional[int] = None

    error_code: Optional[str] = None
    error_message: Optional[str] = None
    failed_stage: Optional[str] = None

    created_at: int = Field(default_factory=now_ts)
    updated_at: int = Field(default_factory=now_ts)


class SpiderCallbackRequest(DomainModel):
    status: str  # SUCCESS|FAILED|...
    task_id: Optional[int] = None
    run_id: Optional[int] = None
    site_code: Optional[str] = None
    run_type: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class VocModuleOutput(DomainModel):
    job_id: int
    module_code: str
    schema_version: int = 1
    payload_json: Dict[str, Any]
    created_at: int = Field(default_factory=now_ts)
    updated_at: int = Field(default_factory=now_ts)
