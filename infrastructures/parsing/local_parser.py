# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import threading
from typing import Callable, Any, Dict, Optional, cast

from infrastructures.parsing.docx_parser import DocxParser
from infrastructures.parsing.parser_base import Parser
from infrastructures.parsing.parser_router import ParserRouter
from infrastructures.parsing.pdf_parser import PdfParser
from infrastructures.parsing.text_parser import TextParser
from infrastructures.vconfig import vconfig


class _LazyInit:
    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._impl: Any = None
        self._lock = threading.Lock()

    def _get(self) -> Any:
        if self._impl is not None:
            return self._impl
        with self._lock:
            if self._impl is None:
                self._impl = self._factory()
        return self._impl

    async def parse(self, *, storage_uri: str, content_type: str) -> Dict[str, Any]:
        impl = self._get()
        return await impl.parse(storage_uri=storage_uri, content_type=content_type)


def _make_image_parser() -> Any:
    from infrastructures.parsing.image_ocr_parser import PaddleOcrParser

    return PaddleOcrParser(lang=vconfig.ocr_lang)


def _make_audio_parser() -> Any:
    from infrastructures.parsing.audio_asr_parser import FasterWhisperParser

    return FasterWhisperParser(
        model_size=vconfig.whisper_model_size,
        device=vconfig.whisper_device,
        compute_type=vconfig.whisper_compute_type,
        language=vconfig.whisper_language,
    )


class LocalParser:
    def __init__(self) -> None:
        enable_image_ocr = bool(vconfig.enable_image_ocr)
        enable_audio_asr = bool(vconfig.enable_audio_asr)

        image_parser: Optional[Parser] = None
        audio_parser: Optional[Parser] = None

        if enable_image_ocr:
            image_parser = cast(Parser, cast(object, _LazyInit(_make_image_parser)))
        if enable_audio_asr:
            audio_parser = cast(Parser, cast(object, _LazyInit(_make_audio_parser)))

        self.router = ParserRouter(
            text_parser=TextParser(),
            pdf_parser=PdfParser(),
            docx_parser=DocxParser(),
            image_parser=image_parser,
            audio_parser=audio_parser,
            enable_image_ocr=enable_image_ocr,
            enable_audio_asr=enable_audio_asr,
        )

    async def parse(self, *, storage_uri: str, content_type: str) -> Dict[str, Any]:
        return await self.router.parse(storage_uri=storage_uri, content_type=content_type)
