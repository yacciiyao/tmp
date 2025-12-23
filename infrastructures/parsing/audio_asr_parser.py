# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import asyncio
from typing import Optional, Dict, Any, List

from infrastructures.vconfig import vconfig

if vconfig.enable_audio_asr:
    from faster_whisper import WhisperModel
else:
    WhisperModel = None

from infrastructures.parsing.parser_base import Parser, ParseError


class FasterWhisperParser(Parser):
    def __init__(
            self,
            *,
            model_size: str = "base",
            device: str = "cpu",
            compute_type: str = "int8",
            language: Optional[str] = None,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None  # lazy

    async def parse(self, *, storage_uri: str, content_type: str) -> Dict[str, Any]:
        path = self._to_local_path(storage_uri)
        text, elements = await asyncio.to_thread(self._asr_sync, path)
        if not text.strip():
            raise ParseError("asr returned empty text", retryable=False)
        return {"text": text, "elements": elements, "source_modality": "audio"}

    def _get_model(self):
        if self._model is not None:
            return self._model

        if WhisperModel is None:
            raise ParseError("audio ASR is disabled or faster-whisper is not installed", retryable=False)

        self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model

    def _asr_sync(self, path: str) -> tuple[str, List[Dict[str, Any]]]:
        model = self._get_model()
        segments, _info = model.transcribe(path, language=self.language, vad_filter=True)

        parts: List[str] = []
        elements: List[Dict[str, Any]] = []
        for seg in segments:
            t = (seg.text or "").strip()
            if not t:
                continue
            parts.append(t)
            elements.append({"type": "text", "text": t, "locator": {"start": float(seg.start), "end": float(seg.end)}})

        return "\n".join(parts), elements
