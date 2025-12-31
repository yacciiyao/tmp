# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Provider-agnostic LLM request/response contracts (no business logic).

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import Field

from domains.domain_base import DomainModel


class LlmRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class InputPartType(str, Enum):
    text = "text"
    image = "image"
    audio = "audio"
    file = "file"


class LlmOutputFormat(str, Enum):
    text = "text"
    json = "json"


class StreamEventType(str, Enum):
    delta_text = "delta.text"
    delta_json = "delta.json"
    tool_call = "tool.call"
    tool_result = "tool.result"
    completed = "response.completed"
    error = "error"


class TextPart(DomainModel):
    type: InputPartType = Field(default=InputPartType.text)
    text: str = Field(..., min_length=1)


class ImagePart(DomainModel):
    type: InputPartType = Field(default=InputPartType.image)
    # asset_uri points to the local/object storage entry, not a public URL.
    asset_uri: str = Field(..., min_length=1)
    mime_type: str = Field("image/png")


class AudioPart(DomainModel):
    type: InputPartType = Field(default=InputPartType.audio)
    asset_uri: str = Field(..., min_length=1)
    mime_type: str = Field("audio/wav")


class FilePart(DomainModel):
    type: InputPartType = Field(default=InputPartType.file)
    asset_uri: str = Field(..., min_length=1)
    mime_type: str = Field("application/pdf")
    file_name: Optional[str] = Field(default=None)


InputPart = Union[TextPart, ImagePart, AudioPart, FilePart]


class OutputContract(DomainModel):
    format: LlmOutputFormat = Field(default=LlmOutputFormat.text)
    strict_json: bool = Field(default=False)
    json_schema: Optional[Dict[str, Any]] = Field(default=None)


class LlmMessage(DomainModel):
    role: LlmRole = Field(...)
    content: str = Field("", description="Text-only content. For multimodal, use input_parts.")


class LlmRequest(DomainModel):
    """Provider-agnostic request.

    This contract is intentionally minimal and does not enforce a specific provider's schema.
    """

    use_case: str = Field(..., min_length=3, max_length=64)
    # profile_id is the chosen model profile (session-locked). Routing is handled outside.
    model_profile_id: str = Field(..., min_length=3, max_length=128)

    stream: bool = Field(default=False)
    timeout_seconds: int = Field(default=60, ge=1)

    system_prompt: Optional[str] = Field(default=None)
    messages: List[LlmMessage] = Field(default_factory=list)
    input_parts: List[InputPart] = Field(default_factory=list)

    output_contract: OutputContract = Field(default_factory=OutputContract)

    # Observability & idempotency
    trace_id: Optional[str] = Field(default=None)
    extra: Dict[str, Any] = Field(default_factory=dict)


class LlmUsage(DomainModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class LlmResponse(DomainModel):
    provider: str = Field(...)
    model: str = Field(...)
    latency_ms: int = Field(default=0, ge=0)
    text: Optional[str] = Field(default=None)
    json: Optional[Dict[str, Any]] = Field(default=None)
    usage: LlmUsage = Field(default_factory=LlmUsage)
    raw: Dict[str, Any] = Field(default_factory=dict)


class StreamEvent(DomainModel):
    type: StreamEventType = Field(...)
    delta: Optional[str] = Field(default=None)
    json_delta: Optional[Dict[str, Any]] = Field(default=None)
    raw: Dict[str, Any] = Field(default_factory=dict)
