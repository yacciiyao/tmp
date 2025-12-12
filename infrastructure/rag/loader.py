# -*- coding: utf-8 -*-
# @File: infrastructure/rag/loader.py
# @Description: 文本加载与简单抽取（file/url/text）+ 降级策略

from __future__ import annotations

from typing import Any, Dict, Optional
import asyncio

from infrastructure import mlogger
from infrastructure.storage.path_utils import resolve_from_relative

import httpx
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
import docx2txt


async def _read_file_bytes(abs_path: str) -> bytes:
    def _read() -> bytes:
        with open(abs_path, "rb") as f:
            return f.read()
    return await asyncio.to_thread(_read)


def _bytes_to_text(data: bytes, mime_type: Optional[str]) -> str:
    # 最朴素的“猜测编码”策略，优先 utf-8
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore")


def _extract_text_from_html(html: str) -> str:
    if BeautifulSoup is None:
        return html
    soup = BeautifulSoup(html, "html.parser")
    # 去掉脚本/样式/不可见
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    # 兼容旧版 bs4：不要使用 get_text(separator=...)
    lines = [s.strip() for s in soup.stripped_strings]
    return "\n".join([ln for ln in lines if ln])


async def load_content(
    *,
    source_type: str,
    source_uri: str,
    mime_type: Optional[str],
    extra_meta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    统一入口：
      - file: 通过相对路径定位本地文件，尽力抽文本（txt/pdf/docx/html）
      - url:  用 httpx 拉取，若是 html 尝试去标签
      - text: 直接取 extra_meta['text']（或 source_uri 本身）
    """
    source_type = (source_type or "file").lower().strip()

    if source_type == "text":
        if extra_meta and isinstance(extra_meta.get("text"), str):
            return str(extra_meta["text"])
        return source_uri or ""

    if source_type == "url":
        if not httpx:
            raise RuntimeError("httpx not installed")
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:  # type: ignore
            resp = await client.get(source_uri)
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "")
            body = resp.content
            if "html" in ctype:
                return _extract_text_from_html(_bytes_to_text(body, "text/html"))
            return _bytes_to_text(body, ctype)

    # 默认 file
    abs_path = resolve_from_relative(source_uri)
    abs_path_str = str(abs_path)  # 统一转为 str，避免 Path 类型导致的类型检查/调用问题
    raw = await _read_file_bytes(abs_path_str)

    mt = (mime_type or "").lower()

    # 1) 纯文本
    if mt.startswith("text/") or mt in ("application/json", "application/xml"):
        return _bytes_to_text(raw, mt)

    # 2) PDF
    if mt == "application/pdf" or abs_path_str.lower().endswith(".pdf"):
        if PdfReader is None:
            mlogger.warning("loader", "pdf_no_dep", path=abs_path_str)
            return _bytes_to_text(raw, mt)
        text_parts = []
        try:
            reader = PdfReader(abs_path_str)
            for p in reader.pages:
                try:
                    text_parts.append(p.extract_text() or "")
                except Exception:
                    continue
            return "\n".join([t for t in text_parts if t])
        except Exception as e:
            mlogger.warning("loader", "pdf_extract_fail", path=abs_path_str, error=str(e))
            return _bytes_to_text(raw, mt)

    # 3) DOCX
    if mt in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",) or abs_path_str.lower().endswith(".docx"):
        if docx2txt is None:
            mlogger.warning("loader", "docx_no_dep", path=abs_path_str)
            return _bytes_to_text(raw, mt)
        try:
            text = await asyncio.to_thread(docx2txt.process, abs_path_str)
            return text or ""
        except Exception as e:
            mlogger.warning("loader", "docx_extract_fail", path=abs_path_str, error=str(e))
            return _bytes_to_text(raw, mt)

    # 4) HTML
    if mt in ("text/html",) or abs_path_str.lower().endswith((".htm", ".html")):
        return _extract_text_from_html(_bytes_to_text(raw, "text/html"))

    # 5) 其它（图片/音频/视频等）——此处不做 OCR/ASR，留给会话多模态链路
    mlogger.info("loader", "binary_fallback", path=abs_path_str, mime=mt)
    return _bytes_to_text(raw, mt)
