# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC output/evidence domain models

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import Field

from domains.domain_base import DomainModel, now_ts


class VocModuleOutput(DomainModel):
    """Normalized output wrapper saved in stg_voc_outputs.payload_json.

    v1 focuses on structured data (tables/charts) + optional ai_summary.
    """

    available: bool = True
    module_code: str
    schema_version: int = 1

    data: Dict[str, Any] = Field(default_factory=dict)
    ai_summary: Optional[str] = None

    meta: Dict[str, Any] = Field(default_factory=dict)
    generated_at: int = Field(default_factory=now_ts)


class VocEvidenceItem(DomainModel):
    evidence_id: int
    job_id: int
    module_code: str

    source_type: str
    source_id: int
    kind: Optional[str] = None

    snippet: str
    meta_json: Dict[str, Any] = Field(default_factory=dict)

    created_at: int
    updated_at: int