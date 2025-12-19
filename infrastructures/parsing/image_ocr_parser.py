# -*- coding: utf-8 -*-
# @File: image_ocr_parser.py
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from infrastructures.parsing.parser_base import Parser, ParseError
from infrastructures.vconfig import config

# Optional dependency: only required when image OCR is enabled.
if config.enable_image_ocr:
    from paddleocr import PaddleOCR  # type: ignore
else:  # pragma: no cover
    PaddleOCR = None  # type: ignore


class PaddleOcrParser(Parser):
    """
    PaddleOCR 3.x（PaddleX 推理管线）：
      - ocr.predict(path) -> iterable of result objects
      - result.json 属性/方法包含识别文本与坐标等信息
    """

    def __init__(self, *, lang: str = "ch") -> None:
        self.lang = lang
        self._ocr = None  # lazy

    async def parse(self, *, storage_uri: str, content_type: str) -> Dict[str, Any]:
        path = self._to_local_path(storage_uri)

        try:
            text, elements = await asyncio.to_thread(self._ocr_sync, path)
        except ParseError:
            raise
        except Exception as e:
            raise ParseError(f"paddleocr parse failed: {e}", retryable=True) from e

        if not text.strip():
            raise ParseError("ocr returned empty text", retryable=False)

        return {"text": text, "elements": elements, "source_modality": "image"}

    def _to_local_path(self, storage_uri: str) -> str:
        if storage_uri.startswith("local:"):
            return storage_uri[len("local:") :]
        raise ParseError(f"unsupported storage_uri: {storage_uri}", retryable=False)

    def _get_ocr(self):
        if self._ocr is not None:
            return self._ocr

        if PaddleOCR is None:
            raise ParseError("image OCR is disabled or paddleocr is not installed", retryable=False)

        # PaddleOCR 3.x：尽量只传最少参数，避免 Unknown argument
        try:
            self._ocr = PaddleOCR(lang=self.lang)
        except Exception as e:
            raise ParseError(f"init PaddleOCR failed: {e}", retryable=False) from e

        return self._ocr

    def _ocr_sync(self, path: str) -> tuple[str, List[Dict[str, Any]]]:
        ocr = self._get_ocr()

        try:
            results = ocr.predict(path)
        except Exception as e:
            raise ParseError(f"paddleocr predict failed: {e}", retryable=True) from e

        lines: List[str] = []
        elements: List[Dict[str, Any]] = []

        if results is None:
            return "", []

        for res in results:
            j = self._result_json(res)
            if not isinstance(j, dict):
                continue

            r = j.get("res") or {}
            rec_texts = r.get("rec_texts") or []
            rec_scores = r.get("rec_scores") or []
            rec_polys = r.get("rec_polys") or []

            for i, txt in enumerate(rec_texts):
                t = str(txt).strip()
                if not t:
                    continue

                score: Optional[float] = None
                if i < len(rec_scores) and rec_scores[i] is not None:
                    try:
                        score = float(rec_scores[i])
                    except Exception:
                        score = None

                poly = None
                if i < len(rec_polys):
                    poly = rec_polys[i]

                lines.append(t)
                elements.append(
                    {
                        "type": "text",
                        "text": t,
                        "score": score,
                        "polygon": poly,
                    }
                )

        return "\n".join(lines).strip(), elements

    def _result_json(self, res) -> Optional[Dict[str, Any]]:
        """
        PaddleOCR 3.x 文档：Result 对象支持通过 `json` 属性获取预测结果（json 格式）。:contentReference[oaicite:1]{index=1}
        不同版本可能表现为：
          - res.json 是 dict
          - res.json 是 str(JSON)
          - res.json() 是 callable
        """
        if res is None:
            return None

        j = getattr(res, "json", None)
        if j is None:
            return None

        # callable: res.json()
        if callable(j):
            try:
                out = j()
            except Exception:
                return None
        else:
            out = j

        if isinstance(out, dict):
            return out

        if isinstance(out, str):
            s = out.strip()
            if not s:
                return None
            try:
                parsed = json.loads(s)
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None

        return None
