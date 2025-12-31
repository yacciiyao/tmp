# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: LLM session/message/attachment domain models (data only).

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from domains.domain_base import DomainModel


class LlmSessionStatus(str, Enum):
    draft = "DRAFT"  # no messages and no uploads; model can be chosen
    active = "ACTIVE"  # started or uploaded; model locked
    closed = "CLOSED"


class LlmMessageStatus(str, Enum):
    pending = "PENDING"
    generating = "GENERATING"
    done = "DONE"
    failed = "FAILED"


class AttachmentType(str, Enum):
    image = "image"
    audio = "audio"
    file = "file"


class LlmAttachment(DomainModel):
    asset_id: str = Field(..., min_length=3, max_length=64)
    type: AttachmentType = Field(...)
    mime_type: str = Field(..., min_length=3, max_length=128)
    file_name: Optional[str] = Field(default=None)
    size_bytes: int = Field(default=0, ge=0)
    asset_uri: str = Field(..., min_length=1)
    meta: Dict[str, Any] = Field(default_factory=dict)


class LlmSession(DomainModel):
    session_id: str = Field(..., min_length=8, max_length=64)
    user_id: int = Field(..., ge=1)
    flow_code: str = Field(..., min_length=3, max_length=64)

    status: LlmSessionStatus = Field(default=LlmSessionStatus.draft)
    model_profile_id: str = Field(..., min_length=3, max_length=128)

    rag_default: bool = Field(default=False)
    stream_default: bool = Field(default=True)

    attachments: List[LlmAttachment] = Field(default_factory=list)
    created_at: int = Field(default=0, ge=0)
    updated_at: int = Field(default=0, ge=0)


class LlmMessage(DomainModel):
    message_id: int = Field(..., ge=1)
    session_id: str = Field(..., min_length=8, max_length=64)
    role: str = Field(..., min_length=1, max_length=16)
    content: str = Field(default="")

    rag_enabled: Optional[bool] = Field(default=None, description="nullable: inherit session")
    stream_enabled: Optional[bool] = Field(default=None, description="nullable: inherit session")

    attachments: List[LlmAttachment] = Field(default_factory=list)

    status: LlmMessageStatus = Field(default=LlmMessageStatus.pending)
    error_code: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)

    created_at: int = Field(default=0, ge=0)
    updated_at: int = Field(default=0, ge=0)


class LlmFeedbackTarget(str, Enum):
    message = "message"
    session = "session"


class LlmFeedback(DomainModel):
    target_type: LlmFeedbackTarget = Field(...)
    target_id: str = Field(..., min_length=1, max_length=64)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    tags: List[str] = Field(default_factory=list)
    text: Optional[str] = Field(default=None)
    created_at: int = Field(default=0, ge=0)
