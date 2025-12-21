# -*- coding: utf-8 -*-
# @File: chunker.py
# @Description: structure-aware chunker (elements -> chunks)

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple


class SimpleChunker:
    def __init__(self, *, max_chars: int = 800, overlap: int = 80) -> None:
        self.max_chars = int(max_chars)
        self.overlap = int(overlap)

    async def chunk(
            self,
            *,
            parsed: Dict[str, Any],
            document_id: int,
            kb_space: str,
            index_version: int,
    ) -> List[Dict[str, Any]]:
        """
        返回 List[chunk_dict]，字段对齐 domains.rag_domain.Chunk（不包含 created_at）：
          chunk_id, document_id, kb_space, index_version, chunk_index,
          modality, locator, content, content_hash
        """
        modality = self._normalize_modality(str(parsed.get("source_modality") or "text"))

        segs = self._build_segments(
            elements=parsed.get("elements"),
            fallback_text=str(parsed.get("text") or ""),
        )
        if not segs:
            return []

        max_chars = max(100, self.max_chars)
        overlap = max(0, min(self.overlap, max_chars // 2))

        chunks: List[Dict[str, Any]] = []
        buf_text_parts: List[str] = []
        buf_locs: List[Dict[str, Any]] = []
        buf_start_char: Optional[int] = None
        global_char = 0  # 逻辑字符偏移（用于 char_start/char_end）

        def flush_chunk(chunk_index: int) -> None:
            nonlocal buf_text_parts, buf_locs, buf_start_char

            content = "\n".join([p for p in buf_text_parts if p]).strip()
            if not content:
                buf_text_parts = []
                buf_locs = []
                buf_start_char = None
                return

            char_start = int(buf_start_char or 0)
            char_end = int(char_start + len(content))

            locator = self._merge_locator(buf_locs, char_start=char_start, char_end=char_end)

            chunk_id = self._sha1_hex(f"{int(document_id)}:{int(index_version)}:{int(chunk_index)}")
            content_hash = self._sha256_hex(content.encode("utf-8"))
            token_count = self._estimate_token_count(content)

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": int(document_id),
                    "kb_space": str(kb_space),
                    "index_version": int(index_version),
                    "chunk_index": int(chunk_index),
                    "modality": modality,
                    "locator": locator,
                    "content": content,
                    "content_hash": content_hash,
                    "token_count": int(token_count),

                }
            )

            # overlap：保留末尾 overlap 字符（简单实现）
            if overlap > 0 and len(content) > overlap:
                tail = content[-overlap:]
                buf_text_parts = [tail]
                buf_locs = [buf_locs[-1]] if buf_locs else []
                buf_start_char = char_end - overlap
            else:
                buf_text_parts = []
                buf_locs = []
                buf_start_char = None

        chunk_index = 0

        for seg_text, seg_loc in segs:
            seg_text = (seg_text or "").strip()
            if not seg_text:
                continue

            pieces = self._split_large(seg_text, max_chars=max_chars)
            for piece in pieces:
                piece = piece.strip()
                if not piece:
                    continue

                if buf_start_char is None:
                    buf_start_char = global_char

                projected_len = len("\n".join(buf_text_parts + [piece]))
                if projected_len > max_chars and buf_text_parts:
                    flush_chunk(chunk_index)
                    chunk_index += 1
                    if buf_start_char is None:
                        buf_start_char = global_char

                buf_text_parts.append(piece)
                if isinstance(seg_loc, dict) and seg_loc:
                    buf_locs.append(seg_loc)

                global_char += len(piece) + 1  # +1 for newline

        if buf_text_parts:
            flush_chunk(chunk_index)

        return chunks

    def _build_segments(self, *, elements: Any, fallback_text: str) -> List[Tuple[str, Dict[str, Any]]]:
        segs: List[Tuple[str, Dict[str, Any]]] = []

        if isinstance(elements, list) and elements:
            for e in elements:
                if not isinstance(e, dict):
                    continue
                txt = e.get("text")
                if not isinstance(txt, str) or not txt.strip():
                    continue
                loc = e.get("locator") if isinstance(e.get("locator"), dict) else {}
                segs.append((txt, loc))
            return segs

        t = (fallback_text or "").strip()
        if t:
            segs.append((t, {}))
        return segs

    def _split_large(self, text: str, *, max_chars: int) -> List[str]:
        if len(text) <= max_chars:
            return [text]
        out: List[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + max_chars)
            out.append(text[start:end])
            start = end
        return out

    def _merge_locator(self, locs: List[Dict[str, Any]], *, char_start: int, char_end: int) -> Dict[str, Any]:
        locator: Dict[str, Any] = {"char_start": int(char_start), "char_end": int(char_end)}

        pages = []
        starts = []
        ends = []
        bboxes = []

        for loc in locs or []:
            if not isinstance(loc, dict):
                continue
            if "page" in loc:
                try:
                    pages.append(int(loc["page"]))
                except (TypeError, ValueError):
                    pass
            if "start" in loc:
                try:
                    starts.append(float(loc["start"]))
                except (TypeError, ValueError):
                    pass
            if "end" in loc:
                try:
                    ends.append(float(loc["end"]))
                except (TypeError, ValueError):
                    pass
            if "bbox" in loc:
                bboxes.append(loc["bbox"])

        if pages:
            locator["pages"] = sorted(set(pages))
        if starts and ends:
            locator["time_range"] = {"start": float(min(starts)), "end": float(max(ends))}
        if bboxes:
            locator["bboxes"] = bboxes[:50]

        return locator

    def _normalize_modality(self, m: str) -> str:
        m = (m or "text").strip().lower()
        if m in {"text", "image", "audio"}:
            return m
        return "text"

    def _sha1_hex(self, s: str) -> str:
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    def _sha256_hex(self, b: bytes) -> str:
        return hashlib.sha256(b).hexdigest()

    def _estimate_token_count(self, text: str) -> int:
        """
        轻量 token 数估算（用于上下文预算与排序特征）
        - CJK 字符：按 1 计
        - 英文/数字连续串：按“词”计
        说明：这是估算值，不依赖第三方 tokenizer；如需精确，可在 embedder 层统一接入真实 tokenizer。
        """

        if not text:
            return 0
        cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
        words = len(re.findall(r"[A-Za-z0-9]+", text))
        other = len(re.findall(r"[^\s\u4e00-\u9fffA-Za-z0-9]", text))
        return int(cjk + words + (other // 4))
