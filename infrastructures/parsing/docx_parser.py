# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import Any, Dict, List

from docx import Document

from infrastructures.parsing.parser_base import Parser, ParseError


class DocxParser(Parser):
    async def parse(self, *, storage_uri: str, content_type: str) -> Dict[str, Any]:
        path = self._to_local_path(storage_uri)

        try:
            doc = Document(path)
        except Exception as e:
            raise ParseError(f"docx open failed: {e}", retryable=False) from e

        parts: List[str] = []
        elements: List[Dict[str, Any]] = []

        # 1) paragraphs
        for p in getattr(doc, "paragraphs", []) or []:
            t = str(getattr(p, "text", "") or "").strip()
            if not t:
                continue
            parts.append(t)
            elements.append({"type": "text", "text": t, "source": "paragraph"})

        # 2) tables
        for table in getattr(doc, "tables", []) or []:
            for row in getattr(table, "rows", []) or []:
                for cell in getattr(row, "cells", []) or []:
                    for p in getattr(cell, "paragraphs", []) or []:
                        t = str(getattr(p, "text", "") or "").strip()
                        if not t:
                            continue
                        parts.append(t)
                        elements.append({"type": "text", "text": t, "source": "table"})

        # 3) headers/footers
        for section in getattr(doc, "sections", []) or []:
            header = getattr(section, "header", None)
            if header is not None:
                for p in getattr(header, "paragraphs", []) or []:
                    t = str(getattr(p, "text", "") or "").strip()
                    if not t:
                        continue
                    parts.append(t)
                    elements.append({"type": "text", "text": t, "source": "header"})

            footer = getattr(section, "footer", None)
            if footer is not None:
                for p in getattr(footer, "paragraphs", []) or []:
                    t = str(getattr(p, "text", "") or "").strip()
                    if not t:
                        continue
                    parts.append(t)
                    elements.append({"type": "text", "text": t, "source": "footer"})

        text = "\n".join(parts).strip()

        if not text:
            text = "[NO_EXTRACTABLE_TEXT_IN_DOCX]"
            elements.append(
                {
                    "type": "text",
                    "text": text,
                    "source": "placeholder",
                }
            )

        return {
            "text": text,
            "elements": elements,
            "source_modality": "docx_text_only",
        }
