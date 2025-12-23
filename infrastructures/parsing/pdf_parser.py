# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import Dict, Any, List

from pypdf import PdfReader

from infrastructures.parsing.parser_base import Parser, ParseError


class PdfParser(Parser):
    async def parse(self, *, storage_uri: str, content_type: str) -> Dict[str, Any]:
        path = self._to_local_path(storage_uri)

        try:
            reader = PdfReader(path)
        except Exception as e:
            raise ParseError(f"pdf parse failed: {e}", retryable=False) from e

        parts: List[str] = []
        elements: List[Dict[str, Any]] = []
        for i, page in enumerate(reader.pages):
            page_text = (page.extract_text() or "").strip()
            if not page_text:
                continue
            parts.append(page_text)
            elements.append({"type": "text", "text": page_text, "locator": {"page": int(i + 1)}})

        text = "\n".join(parts).strip()
        if not text:
            raise ParseError("pdf has no extractable text", retryable=False)

        return {"text": text, "elements": elements, "source_modality": "pdf"}
