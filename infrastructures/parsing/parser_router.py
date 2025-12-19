# -*- coding: utf-8 -*-
# @File: parser_router.py
# @Author: yaccii
# @Time: 2025-12-15 16:51
# @Description:
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from infrastructures.parsing.parser_base import ParseError, Parser


class ParserRouter:
    def __init__(
        self,
        *,
        text_parser: Parser,
        docx_parser: Parser,
        pdf_parser: Parser,
        image_parser: Optional[Parser] = None,
        audio_parser: Optional[Parser] = None,
        enable_image_ocr: bool = False,
        enable_audio_asr: bool = False,
    ) -> None:
        self.text_parser = text_parser
        self.docx_parser = docx_parser
        self.pdf_parser = pdf_parser
        self.image_parser = image_parser
        self.audio_parser = audio_parser
        self.enable_image_ocr = bool(enable_image_ocr)
        self.enable_audio_asr = bool(enable_audio_asr)

    async def parse(self, *, storage_uri: str, content_type: str) -> Dict[str, Any]:
        ctype = (content_type or "").lower()
        path = storage_uri[len("local:") :] if storage_uri.startswith("local:") else storage_uri
        ext = os.path.splitext(path)[1].lower()

        # PDF
        if "pdf" in ctype or ext == ".pdf":
            return await self.pdf_parser.parse(storage_uri=storage_uri, content_type=content_type)

        if (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in ctype
            or ext == ".docx"
        ):
            if self.docx_parser is None:
                raise ParseError("docx parser not configured", retryable=False)
            return await self.docx_parser.parse(storage_uri=storage_uri, content_type=content_type)

        # Image（关键：不允许 fallback 到 text）
        if ctype.startswith("image/") or ext in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"}:
            if not self.enable_image_ocr or self.image_parser is None:
                raise ParseError("image parsing disabled (ENABLE_IMAGE_OCR=false)", retryable=False)
            return await self.image_parser.parse(storage_uri=storage_uri, content_type=content_type)

        # Audio（关键：不允许 fallback 到 text）
        if ctype.startswith("audio/") or ext in {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}:
            if not self.enable_audio_asr or self.audio_parser is None:
                raise ParseError("audio parsing disabled (ENABLE_AUDIO_ASR=false)", retryable=False)
            return await self.audio_parser.parse(storage_uri=storage_uri, content_type=content_type)

        # Fallback: text
        return await self.text_parser.parse(storage_uri=storage_uri, content_type=content_type)
