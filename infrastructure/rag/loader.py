# -*- coding: utf-8 -*-
# @File: infrastructure/rag/loader.py
# @Author: yaccii
# @Description: RAG 文档加载器（从 file/url/text 获取原始文本）

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

import httpx

from infrastructure import mlogger


async def _read_text_file(path: str, encoding: str = "utf-8") -> str:
    """
    读取纯文本文件（txt/md）。
    """
    def _read() -> str:
        with open(path, "r", encoding=encoding, errors="ignore") as f:
            return f.read()

    return await asyncio.to_thread(_read)


async def _read_pdf_file(path: str) -> str:
    """
    读取 PDF 文本。
    需要依赖 pypdf: pip install pypdf
    """
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "读取 PDF 需要依赖 pypdf，请先安装：pip install pypdf"
        ) from e

    def _read() -> str:
        reader = PdfReader(path)
        texts = []
        for page in reader.pages:
            txt = page.extract_text() or ""
            texts.append(txt)
        return "\n\n".join(texts)

    return await asyncio.to_thread(_read)


async def _load_from_file(path: str, mime_type: Optional[str] = None) -> str:
    """
    根据文件扩展名（或 mime_type）选择合适的读取方式。
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"file not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    if mime_type:
        mime_type = mime_type.lower()

    # 文本类
    if ext in {".txt", ".md"} or (mime_type and mime_type.startswith("text/")):
        return await _read_text_file(path)

    # PDF
    if ext == ".pdf" or (mime_type and "pdf" in mime_type):
        return await _read_pdf_file(path)

    # 其他类型：先不支持（图片/音频/视频 留给多模态管线）
    raise RuntimeError(f"暂不支持的文件类型: {ext or mime_type or 'unknown'}")


async def _load_from_url(url: str) -> str:
    """
    通过 HTTP 拉取文本内容（简版）。
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        # 简单当作 text 处理
        return resp.text


async def load_content(
    source_type: str,
    source_uri: str,
    mime_type: Optional[str] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    RAG 文档统一加载入口：
    - source_type: file / url / text
    - source_uri: 文件路径 / URL / 文本内容或文本 ID
    - mime_type: 可选，用于辅助判断类型
    - extra_meta: 预留，text 模式下可包含 {"text": "..."} 等
    """
    source_type = (source_type or "").lower()
    extra_meta = extra_meta or {}

    if source_type == "file":
        mlogger.info("RAGLoader", "load_content", msg="load file", path=source_uri)
        return await _load_from_file(source_uri, mime_type=mime_type)

    if source_type == "url":
        mlogger.info("RAGLoader", "load_content", msg="load url", url=source_uri)
        return await _load_from_url(source_uri)

    if source_type == "text":
        # 优先从 extra_meta["text"] 取；否则直接用 source_uri
        text = extra_meta.get("text") or source_uri
        mlogger.info("RAGLoader", "load_content", msg="load text", length=len(text))
        return text

    raise ValueError(f"未知的 source_type: {source_type}")
