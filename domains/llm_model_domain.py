# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: LLM model profiles & capability map (DB-backed configuration).

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from domains.domain_base import DomainModel


class LlmProvider(str, Enum):
    openai = "openai"
    gemini = "gemini"
    deepseek = "deepseek"
    qwen = "qwen"
    ollama = "ollama"


class CapabilityMode(str, Enum):
    """Capability mode for a modality.

    - none: not supported
    - assist: supported via deterministic parsing (OCR/ASR/file parsing) and then fed to the chat model as text
    - native: supported natively by the model API
    """

    none = "none"
    assist = "assist"
    native = "native"


class MultimodalPolicy(str, Enum):
    """How to handle unsupported modalities for a session's selected model.

    NOTE: Per the current product rule, model is locked after session starts or any upload.
    Therefore, AUTO_UPGRADE is not recommended for end-user flows.
    """

    block = "BLOCK"  # reject request & ask user to create a new session with a compatible model
    assist = "ASSIST"  # use deterministic parsers (OCR/ASR/file parsing) and continue as text


class LlmModalities(DomainModel):
    input_text: CapabilityMode = Field(default=CapabilityMode.native)
    input_image: CapabilityMode = Field(default=CapabilityMode.none)
    input_audio: CapabilityMode = Field(default=CapabilityMode.none)
    input_file: CapabilityMode = Field(default=CapabilityMode.assist)

    output_text: CapabilityMode = Field(default=CapabilityMode.native)
    output_audio_tts: CapabilityMode = Field(default=CapabilityMode.none)


class LlmFeatures(DomainModel):
    streaming: bool = Field(default=True)
    json_schema: bool = Field(default=True)
    tool_calling: bool = Field(default=False)
    function_calling: bool = Field(default=False)


class LlmLimits(DomainModel):
    max_context_tokens: int = Field(default=0, ge=0)
    max_output_tokens: int = Field(default=0, ge=0)
    max_images_per_request: int = Field(default=0, ge=0)
    max_file_mb: int = Field(default=0, ge=0)
    supported_mime_types: Dict[str, List[str]] = Field(default_factory=dict)


class CapabilityMap(DomainModel):
    modalities: LlmModalities = Field(default_factory=LlmModalities)
    features: LlmFeatures = Field(default_factory=LlmFeatures)
    limits: LlmLimits = Field(default_factory=LlmLimits)
    notes: Optional[str] = Field(default=None)


class LlmModelProfile(DomainModel):
    """A selectable model profile.

    profile_id: stable identifier used across DB/config/cache, e.g.
      - openai:gpt-4.1-mini
      - gemini:gemini-2.0-flash
      - ollama:llama3.2:latest
    """

    profile_id: str = Field(..., min_length=3, max_length=128)
    provider: LlmProvider = Field(...)
    model_name: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=128)

    is_enabled: bool = Field(default=True)
    capabilities: CapabilityMap = Field(default_factory=CapabilityMap)

    meta: Dict[str, Any] = Field(default_factory=dict)


class LlmFlowPolicy(DomainModel):
    """Default model selection & constraints per business flow.

    flow_code examples:
      - chat.general
      - voc.module_summary
      - voc.report_summary
      - parse.vision
      - parse.asr
    """

    flow_code: str = Field(..., min_length=3, max_length=64)
    default_profile_id: str = Field(..., min_length=3, max_length=128)
    allowed_profile_ids: List[str] = Field(default_factory=list)
    fallback_chain: List[str] = Field(default_factory=list)

    default_rag_enabled: bool = Field(default=False)
    default_stream_enabled: bool = Field(default=True)
    multimodal_policy: MultimodalPolicy = Field(default=MultimodalPolicy.block)

    params: Dict[str, Any] = Field(default_factory=dict)
