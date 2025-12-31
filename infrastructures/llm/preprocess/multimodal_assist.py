# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Deterministic multimodal ASSIST preprocessing (OCR/ASR/file parsing).

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from domains.llm_model_domain import CapabilityMode, LlmModelProfile
from domains.llm_request_domain import (
    AudioPart,
    FilePart,
    ImagePart,
    InputPart,
    InputPartType,
    LlmRequest,
    TextPart,
)
from infrastructures.llm.errors import LlmUnsupportedModalityError


def _mode_of(profile: LlmModelProfile, part_type: InputPartType) -> CapabilityMode:
    m = profile.capabilities.modalities
    if part_type == InputPartType.image:
        return m.input_image
    if part_type == InputPartType.audio:
        return m.input_audio
    if part_type == InputPartType.file:
        return m.input_file
    return m.input_text


class MultimodalAssistPreprocessor:
    """Convert non-text parts into text via deterministic parsers.

    This sits *before* provider adapters and is the implementation behind
    CapabilityMode.assist.

    - If a modality is `native`, the part is kept as-is.
    - If a modality is `assist`, the part is parsed into TextPart and the original part is removed.
    - If a modality is `none`, the request is rejected.

    Parsed results are also recorded into req.extra["parsed_inputs"] for debugging.
    """

    def __init__(self, *, parser) -> None:
        # parser must implement: parse(storage_uri=..., content_type=...) -> {"text": ...}
        self._parser = parser

    async def preprocess(self, *, req: LlmRequest, profile: LlmModelProfile) -> LlmRequest:
        if not req.input_parts:
            return req

        # Build output deterministically (preserve original order), while allowing
        # parsing to run concurrently to reduce end-to-end latency.
        out_slots: List[List[InputPart]] = [[] for _ in req.input_parts]
        parsed_meta: List[Dict[str, Any]] = []

        sem = asyncio.Semaphore(4)

        async def _assist_parse(idx: int, part: InputPart) -> Tuple[int, List[InputPart], Dict[str, Any]]:
            # Parse one non-text modality into text.
            async with sem:
                if isinstance(part, ImagePart):
                    parsed = await self._parser.parse(storage_uri=part.asset_uri, content_type=part.mime_type)
                    txt = str(parsed.get("text") or "").strip()
                    out = [TextPart(text=txt)] if txt else []
                    return idx, out, {"type": "image", "asset_uri": part.asset_uri, "text_len": len(txt)}

                if isinstance(part, AudioPart):
                    parsed = await self._parser.parse(storage_uri=part.asset_uri, content_type=part.mime_type)
                    txt = str(parsed.get("text") or "").strip()
                    out = [TextPart(text=txt)] if txt else []
                    return idx, out, {"type": "audio", "asset_uri": part.asset_uri, "text_len": len(txt)}

                if isinstance(part, FilePart):
                    parsed = await self._parser.parse(storage_uri=part.asset_uri, content_type=part.mime_type)
                    txt = str(parsed.get("text") or "").strip()
                    out = [TextPart(text=txt)] if txt else []
                    return idx, out, {
                        "type": "file",
                        "asset_uri": part.asset_uri,
                        "file_name": getattr(part, "file_name", None),
                        "text_len": len(txt),
                    }

            return idx, [], {"type": "unknown", "text_len": 0}

        tasks: List[asyncio.Task] = []

        for idx, p in enumerate(req.input_parts):
            if isinstance(p, TextPart) or getattr(p, "type", None) == InputPartType.text:
                out_slots[idx].append(p)
                continue

            ptype = getattr(p, "type", None)
            if ptype is None:
                continue

            mode = _mode_of(profile, ptype)
            if mode == CapabilityMode.native:
                out_slots[idx].append(p)
                continue

            if mode == CapabilityMode.none:
                raise LlmUnsupportedModalityError(
                    f"model profile does not support modality: {ptype}",
                    provider=profile.provider.value,
                    details={"profile_id": profile.profile_id, "part_type": str(ptype)},
                )

            # assist: schedule parsing concurrently
            tasks.append(asyncio.create_task(_assist_parse(idx, p)))

        if tasks:
            results = await asyncio.gather(*tasks)
            for idx, out, meta in results:
                if out:
                    out_slots[idx].extend(out)
                if meta:
                    parsed_meta.append(meta)

        out_parts: List[InputPart] = []
        for slot in out_slots:
            out_parts.extend(slot)

        extra = dict(req.extra or {})
        if parsed_meta:
            extra["parsed_inputs"] = parsed_meta

        return req.model_copy(update={"input_parts": out_parts, "extra": extra})
