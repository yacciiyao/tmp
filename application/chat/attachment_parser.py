# -*- coding: utf-8 -*-
# @File: application/chat/attachment_parser.py
# @Author: yaccii
# @Description: 会话内临时附件文本抽取（不入向量库）

from __future__ import annotations

from typing import Any, Dict, List
from infrastructure import mlogger
from infrastructure.rag.loader import load_content


class AttachmentTextExtractor:
    """
    把 router 已保存到磁盘的附件，提取出“可用于 LLM 的文本”，仅用于本轮上下文。
    约定：router 传入的每个附件项包含：
        {
            "file_path": "<相对路径>",  # 必填（相对根存储路径）
            "file_url": "<可选-公网直链>",
            "file_name": "<原始文件名>",
            "mime_type": "<MIME>",
            "size_bytes": <int>,
        }
    """

    async def extract_many(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for it in items:
            rel_path = it.get("file_path") or it.get("rel_path") or ""
            mime = it.get("mime_type")
            text = ""
            try:
                if rel_path:
                    # 统一复用 RAG loader 的文件解析能力：txt/json/xml/pdf/docx/html
                    text = await load_content(
                        source_type="file",
                        source_uri=rel_path,
                        mime_type=(mime or ""),
                        extra_meta=None,
                    )
                # 图片/音频/视频当前不做 OCR/ASR，返回空串；后续可接 OCRClient
            except Exception as e:
                mlogger.warning("AttachmentTextExtractor", "extract_fail", error=str(e))

            results.append(
                {
                    "file_path": rel_path or it.get("file_path"),
                    "file_url": it.get("file_url"),
                    "file_name": it.get("file_name"),
                    "mime_type": mime,
                    "size_bytes": it.get("size_bytes"),
                    "text": text or "",
                }
            )
        return results
