# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Capability guard helpers (backend validation). No business logic.

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from domains.llm_model_domain import CapabilityMode, LlmModelProfile


@dataclass
class CapabilityCheckResult:
    ok: bool
    reason: Optional[str] = None


def _supports(mode: CapabilityMode, *, require_native: bool = False) -> bool:
    if require_native:
        return mode == CapabilityMode.native
    return mode in (CapabilityMode.native, CapabilityMode.assist)


def check_request_capabilities(
    profile: LlmModelProfile,
    *,
    need_image: bool = False,
    need_audio: bool = False,
    need_file: bool = False,
    need_stream: bool = False,
    need_json_schema: bool = False,
    require_native_image: bool = False,
    require_native_audio: bool = False,
) -> CapabilityCheckResult:
    """Check whether a model profile can satisfy requested features/modalities.

    This function is used as a backend guard even if the UI hides/disabled controls.
    """

    caps = profile.capabilities

    if need_image and not _supports(caps.modalities.input_image, require_native=require_native_image):
        return CapabilityCheckResult(False, "model_not_support_image")
    if need_audio and not _supports(caps.modalities.input_audio, require_native=require_native_audio):
        return CapabilityCheckResult(False, "model_not_support_audio")
    if need_file and not _supports(caps.modalities.input_file, require_native=False):
        return CapabilityCheckResult(False, "model_not_support_file")

    if need_stream and not bool(caps.features.streaming):
        return CapabilityCheckResult(False, "model_not_support_stream")
    if need_json_schema and not bool(caps.features.json_schema):
        return CapabilityCheckResult(False, "model_not_support_json_schema")

    return CapabilityCheckResult(True)
