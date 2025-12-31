# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Chat + Agent contracts (data only). No business logic.

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import Field

from domains.domain_base import DomainModel


# =========================
# Domain enums
# =========================

class ChatSessionStatus(str, Enum):
    draft = "DRAFT"
    active = "ACTIVE"
    archived = "ARCHIVED"


class ChatMessageStatus(str, Enum):
    pending = "PENDING"
    generating = "GENERATING"
    done = "DONE"
    failed = "FAILED"


class ChatRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class ChatAttachmentType(str, Enum):
    image = "image"
    audio = "audio"
    file = "file"


class ChatFeedbackTarget(str, Enum):
    message = "message"
    session = "session"


class ChatStreamEventType(str, Enum):
    delta = "delta"          # token chunk
    sources = "sources"      # rag sources chunk
    meta = "meta"            # usage/model/trace/tool calls
    error = "error"
    done = "done"


# =========================
# Shared models
# =========================

class RagSource(DomainModel):
    """A single RAG source snippet."""
    source_id: str = Field(..., min_length=1, max_length=128)
    title: Optional[str] = Field(default=None, max_length=256)
    snippet: str = Field(..., min_length=1)
    score: Optional[float] = Field(default=None)
    url: Optional[str] = Field(default=None, max_length=1024)
    meta: Dict[str, Any] = Field(default_factory=dict)


class ModelUsage(DomainModel):
    """Token usage (best-effort)."""
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class ProviderMeta(DomainModel):
    """Execution meta for a single model/tool call."""
    provider: Optional[str] = Field(default=None, max_length=64)
    model: Optional[str] = Field(default=None, max_length=128)
    latency_ms: Optional[int] = Field(default=None, ge=0)
    usage: Optional[ModelUsage] = Field(default=None)
    trace_id: Optional[str] = Field(default=None, max_length=128)


# =========================
# Domain models (data only)
# =========================

class ChatAttachment(DomainModel):
    attachment_id: int = Field(..., ge=1)
    session_id: str = Field(..., min_length=8, max_length=64)
    message_id: Optional[int] = Field(default=None, ge=1)

    type: ChatAttachmentType = Field(...)
    mime_type: str = Field(..., min_length=3, max_length=128)
    file_name: Optional[str] = Field(default=None, max_length=255)
    size_bytes: int = Field(default=0, ge=0)

    asset_uri: str = Field(..., min_length=1)

    # For audio/file: deterministic extracted text (ASR/PDF parsing etc)
    # For image: optional, can store final_context_text (confirmed) for retrieval/debug
    extracted_text: Optional[str] = Field(default=None)

    # For image two-stage:
    #   meta.image_draft: preanalyze output (editable)
    #   meta.image_confirmed: confirmed draft (final)
    # For audit:
    #   meta.vision/asr: provider meta
    meta: Dict[str, Any] = Field(default_factory=dict)

    created_at: int = Field(default=0, ge=0)
    updated_at: int = Field(default=0, ge=0)


class ChatSession(DomainModel):
    session_id: str = Field(..., min_length=8, max_length=64)
    user_id: int = Field(..., ge=1)

    flow_code: str = Field(..., min_length=3, max_length=64)
    model_profile_id: str = Field(..., min_length=3, max_length=128)

    # optional: persona for companion chats (session-level; locked with model)
    persona_id: Optional[str] = Field(default=None, max_length=64)

    status: ChatSessionStatus = Field(default=ChatSessionStatus.draft)
    title: Optional[str] = Field(default=None, max_length=128)

    locked_at: int = Field(
        default=0,
        ge=0,
        description="0 means unlocked. Once locked (>0), model_profile_id/persona_id must not change.",
    )

    rag_default: bool = Field(default=False)
    stream_default: bool = Field(default=True)

    attachments: List[ChatAttachment] = Field(default_factory=list)

    # reserved for extensibility (rolling summary, companion state, etc.)
    meta: Dict[str, Any] = Field(default_factory=dict)

    created_at: int = Field(default=0, ge=0)
    updated_at: int = Field(default=0, ge=0)


class ChatMessage(DomainModel):
    message_id: int = Field(..., ge=1)
    session_id: str = Field(..., min_length=8, max_length=64)

    role: ChatRole = Field(...)
    content: str = Field(default="")
    content_type: str = Field(default="text", min_length=1, max_length=32)

    # nullable means inherit session default
    rag_enabled: Optional[bool] = Field(default=None)
    stream_enabled: Optional[bool] = Field(default=None)

    attachment_ids: List[int] = Field(default_factory=list)

    status: ChatMessageStatus = Field(default=ChatMessageStatus.pending)
    error_code: Optional[str] = Field(default=None, max_length=64)
    error_message: Optional[str] = Field(default=None, max_length=2048)

    # sources/usage/trace/tool calls/model snapshot etc.
    meta: Dict[str, Any] = Field(default_factory=dict)

    created_at: int = Field(default=0, ge=0)
    updated_at: int = Field(default=0, ge=0)


class ChatFeedback(DomainModel):
    target_type: ChatFeedbackTarget = Field(...)
    target_id: str = Field(..., min_length=1, max_length=64)

    rating: Optional[int] = Field(default=None, ge=1, le=5)
    tags: List[str] = Field(default_factory=list)
    text: Optional[str] = Field(default=None, max_length=2000)

    created_at: int = Field(default=0, ge=0)


# =========================
# Two-stage Image (pure VLM) contracts
# =========================

class ImageBBox(DomainModel):
    """Normalized bbox (0~1)."""
    x1: float = Field(..., ge=0.0, le=1.0)
    y1: float = Field(..., ge=0.0, le=1.0)
    x2: float = Field(..., ge=0.0, le=1.0)
    y2: float = Field(..., ge=0.0, le=1.0)


class ImageObjectItem(DomainModel):
    label: str = Field(..., min_length=1, max_length=128)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    bbox: Optional[ImageBBox] = Field(default=None)
    meta: Dict[str, Any] = Field(default_factory=dict)


class ImageOcrBlock(DomainModel):
    text: str = Field(..., min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    bbox: Optional[ImageBBox] = Field(default=None)


class ImageDraft(DomainModel):
    """Editable draft for image understanding.

    final_context_text:
      - deterministic context text to be injected into chat prompt after user confirm
      - should be generated by server at confirm step (based on confirmed draft)
    """

    objects: List[ImageObjectItem] = Field(default_factory=list)
    ocr_blocks: List[ImageOcrBlock] = Field(default_factory=list)

    scene: Optional[str] = Field(default=None, max_length=128)
    caption_suggestion: Optional[str] = Field(default=None, max_length=1000)

    # user editable area
    user_notes: Optional[str] = Field(default=None, max_length=1000)

    # server generated at confirm step
    final_context_text: Optional[str] = Field(default=None, max_length=4000)

    meta: Dict[str, Any] = Field(default_factory=dict)


class ImagePreanalyzeReq(DomainModel):
    """Pure VLM preanalyze.

    require_native_image:
      - must be true for 'pure VLM' requirement (avoid OCR-only assist path)
    """

    user_id: int = Field(..., ge=1)
    session_id: str = Field(..., min_length=8, max_length=64)
    attachment_id: int = Field(..., ge=1)

    require_native_image: bool = Field(default=True)
    prompt_hint: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional hint, e.g. 'identify product defects' / 'extract text only'.",
    )


class ImagePreanalyzeResp(DomainModel):
    attachment_id: int = Field(..., ge=1)
    draft: ImageDraft = Field(...)
    provider_meta: Optional[ProviderMeta] = Field(default=None)


class ImageConfirmReq(DomainModel):
    user_id: int = Field(..., ge=1)
    session_id: str = Field(..., min_length=8, max_length=64)
    attachment_id: int = Field(..., ge=1)

    # user-confirmed draft (may be modified by user)
    draft: ImageDraft = Field(...)


class ImageConfirmResp(DomainModel):
    attachment_id: int = Field(..., ge=1)
    confirmed_draft: ImageDraft = Field(...)
    final_context_text: str = Field(..., min_length=1, max_length=4000)


# =========================
# Audio (transcribe then reply) contracts
# =========================

class AudioTranscribeReq(DomainModel):
    """Transcribe audio to text first, then send as a normal text message."""
    user_id: int = Field(..., ge=1)
    session_id: str = Field(..., min_length=8, max_length=64)
    attachment_id: int = Field(..., ge=1)

    language_hint: Optional[str] = Field(default=None, max_length=32)
    prompt_hint: Optional[str] = Field(default=None, max_length=256)


class AudioTranscribeResp(DomainModel):
    attachment_id: int = Field(..., ge=1)
    transcript: str = Field(..., min_length=1, max_length=20000)
    provider_meta: Optional[ProviderMeta] = Field(default=None)


# =========================
# Image generation contracts (tool-style)
# =========================

class ImageGenSize(str, Enum):
    s_512 = "512x512"
    s_768 = "768x768"
    s_1024 = "1024x1024"
    s_1024_1792 = "1024x1792"
    s_1792_1024 = "1792x1024"


class ImageGenerateReq(DomainModel):
    """Generate images via provider image model (NOT chat completion)."""
    user_id: int = Field(..., ge=1)
    session_id: str = Field(..., min_length=8, max_length=64)

    prompt: str = Field(..., min_length=1, max_length=2000)
    size: ImageGenSize = Field(default=ImageGenSize.s_1024)
    n: int = Field(default=1, ge=1, le=4)

    # optional: for editing/variation, if supported by provider
    referenced_attachment_id: Optional[int] = Field(default=None, ge=1)
    transparent_background: bool = Field(default=False)

    meta: Dict[str, Any] = Field(default_factory=dict)


class ImageGenerateResp(DomainModel):
    images: List[str] = Field(
        default_factory=list,
        description="List of asset_uri (stored) or provider-returned URL (if allowed).",
    )
    provider_meta: Optional[ProviderMeta] = Field(default=None)


# =========================
# Tool/Agent contracts
# =========================

class ToolName(str, Enum):
    # RAG
    rag_search = "rag.search"

    # VOC
    voc_get_latest_report = "voc.get_latest_report"
    voc_create_job = "voc.create_job"
    voc_get_job_status = "voc.get_job_status"
    voc_get_output = "voc.get_output"
    voc_get_evidence = "voc.get_evidence"

    # Image
    image_preanalyze = "image.preanalyze"
    image_confirm = "image.confirm"
    image_generate = "image.generate"


class ToolCall(DomainModel):
    """A single tool call request."""
    call_id: str = Field(..., min_length=8, max_length=64)
    name: ToolName = Field(...)
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(DomainModel):
    """A single tool call result."""
    call_id: str = Field(..., min_length=8, max_length=64)
    name: ToolName = Field(...)
    ok: bool = Field(default=True)

    data: Dict[str, Any] = Field(default_factory=dict)
    error_code: Optional[str] = Field(default=None, max_length=64)
    error_message: Optional[str] = Field(default=None, max_length=2048)

    provider_meta: Optional[ProviderMeta] = Field(default=None)


class AgentDecision(DomainModel):
    """Internal orchestration decision (best-effort).

    mode:
      - direct: normal chat (no tools)
      - tools: tool loop (one or more tool calls)
    """
    mode: str = Field(..., min_length=3, max_length=16)
    reason: Optional[str] = Field(default=None, max_length=500)
    tool_calls: List[ToolCall] = Field(default_factory=list)


# =========================
# VOC tool data contracts (minimal + UI-friendly)
# =========================

class VocReportRef(DomainModel):
    job_id: int = Field(..., ge=1)
    module_code: str = Field(..., min_length=3, max_length=64)
    updated_at: int = Field(default=0, ge=0)


class VocEvidenceItem(DomainModel):
    source_type: str = Field(..., min_length=1, max_length=32)
    source_id: Union[int, str] = Field(...)
    snippet: str = Field(..., min_length=1, max_length=1000)
    meta: Dict[str, Any] = Field(default_factory=dict)


class VocOutputItem(DomainModel):
    job_id: int = Field(..., ge=1)
    module_code: str = Field(..., min_length=3, max_length=64)
    schema_version: int = Field(default=1, ge=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    updated_at: int = Field(default=0, ge=0)


# =========================
# API contracts (data only)
# =========================

class CreateSessionReq(DomainModel):
    """Create a new session or reuse an empty draft session.

    Rule:
      - If reuse_empty=true, service may return an existing DRAFT session (no messages, no attachments).
      - model_profile_id/persona_id can only be set/changed when session is still unlocked.
    """

    user_id: int = Field(..., ge=1)
    flow_code: str = Field("chat.general", min_length=3, max_length=64)

    model_profile_id: Optional[str] = Field(default=None, min_length=3, max_length=128)
    persona_id: Optional[str] = Field(default=None, max_length=64)
    title: Optional[str] = Field(default=None, max_length=128)

    reuse_empty: bool = Field(default=True)
    rag_default: Optional[bool] = Field(default=None)
    stream_default: Optional[bool] = Field(default=None)


class CreateSessionResp(DomainModel):
    session: ChatSession = Field(...)
    reused: bool = Field(default=False)


class ListSessionsReq(DomainModel):
    user_id: int = Field(..., ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ListSessionsResp(DomainModel):
    total: int = Field(default=0, ge=0)
    items: List[ChatSession] = Field(default_factory=list)


class UpdateSessionReq(DomainModel):
    """Update mutable fields for a session.

    NOTE: model_profile_id/persona_id is intentionally NOT included here.
    """

    title: Optional[str] = Field(default=None, max_length=128)
    status: Optional[str] = Field(default=None, description="Allow setting ARCHIVED/ACTIVE by API")
    meta: Optional[Dict[str, Any]] = Field(default=None)


class UploadAttachmentReq(DomainModel):
    """Upload an attachment to a session.

    asset_uri may refer to a stored object (local/s3) or an existing object key.
    """

    session_id: str = Field(..., min_length=8, max_length=64)
    user_id: int = Field(..., ge=1)

    type: ChatAttachmentType = Field(...)
    mime_type: str = Field(..., min_length=3, max_length=128)
    file_name: Optional[str] = Field(default=None, max_length=255)
    size_bytes: int = Field(default=0, ge=0)

    asset_uri: str = Field(..., min_length=1)


class UploadAttachmentResp(DomainModel):
    attachment: ChatAttachment = Field(...)


class SendMessageReq(DomainModel):
    """Send one user message to a session.

    stream:
      - if true, server should respond with SSE streaming chunks
      - if false, server returns a full response

    agent_enabled:
      - if true, server may route to tool loop based on intent
      - if false, always direct chat (still can use rag_enabled)
    """

    session_id: str = Field(..., min_length=8, max_length=64)
    user_id: int = Field(..., ge=1)

    content: str = Field("", description="User text input")
    content_type: str = Field(default="text", min_length=1, max_length=32)

    attachment_ids: List[int] = Field(default_factory=list)

    rag_enabled: Optional[bool] = Field(default=None)
    stream_enabled: Optional[bool] = Field(default=None)

    agent_enabled: bool = Field(default=True)

    # reserved for extensibility (tool hints, ui action, etc.)
    extra: Dict[str, Any] = Field(default_factory=dict)


class SendMessageResp(DomainModel):
    user_message: ChatMessage = Field(...)
    assistant_message: ChatMessage = Field(...)


class ChatStreamEvent(DomainModel):
    type: ChatStreamEventType = Field(...)
    data: Dict[str, Any] = Field(default_factory=dict)


class CreateFeedbackReq(DomainModel):
    user_id: int = Field(..., ge=1)
    target_type: ChatFeedbackTarget = Field(...)
    target_id: str = Field(..., min_length=1, max_length=64)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    tags: List[str] = Field(default_factory=list)
    text: Optional[str] = Field(default=None, max_length=2000)


class CreateFeedbackResp(DomainModel):
    ok: bool = Field(default=True)
