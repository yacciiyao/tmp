# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import Any, Dict, List

from infrastructures.parsing.parser_base import Parser, ParseError


class TextParser(Parser):
    async def parse(self, *, storage_uri: str, content_type: str) -> Dict[str, Any]:
        path = self._to_local_path(storage_uri)

        # 防止图片/音频/octet-stream 走到 text fallback 后乱码
        if self._looks_binary(path):
            raise ParseError("file looks like binary; text parser refused", retryable=False)

        text = self._read_text(path)

        elements: List[Dict[str, Any]] = []
        if text.strip():
            elements.append({"type": "text", "text": text, "locator": None})

        return {"text": text, "elements": elements, "source_modality": "text"}

    @staticmethod
    def _looks_binary(path: str) -> bool:
        try:
            with open(path, "rb") as f:
                b = f.read(4096)
        except OSError as e:
            raise ParseError(f"read file failed: {e}", retryable=False) from e

        if not b:
            return False
        if b"\x00" in b:
            return True
        printable = sum(1 for x in b if 32 <= x <= 126 or x in (9, 10, 13))
        return printable / max(1, len(b)) < 0.70

    @staticmethod
    def _read_text(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="latin-1", errors="ignore") as f:
                return f.read()
