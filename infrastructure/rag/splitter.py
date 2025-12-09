# -*- coding: utf-8 -*-
# @File: infrastructure/rag/splitter.py
# @Author: yaccii
# @Description: RAG 文本切分器（段落 + 滑动窗口）

from __future__ import annotations

import re
from typing import List


def split_text(
    text: str,
    max_chars: int = 800,
    overlap: int = 200,
) -> List[str]:
    """
    简单文本切分策略：
    1. 按空行拆段（段落级）
    2. 对超长段落按 max_chars 做滑动窗口切分，窗口之间 overlap 字符重叠

    不做 token 级精细控制，后续如需要可接入 tiktoken / tokenizer 再升级。
    """
    text = text or ""
    text = text.strip()
    if not text:
        return []

    # 先按空行拆段
    raw_paragraphs = re.split(r"\n\s*\n+", text)
    paragraphs = [p.strip() for p in raw_paragraphs if p and p.strip()]

    chunks: List[str] = []

    for para in paragraphs:
        if len(para) <= max_chars:
            chunks.append(para)
            continue

        # 超长段落按窗口切
        start = 0
        length = len(para)
        while start < length:
            end = start + max_chars
            chunk = para[start:end]
            chunk = chunk.strip()
            if chunk:
                chunks.append(chunk)
            if end >= length:
                break
            # 下一个窗口起点
            start = end - overlap

    # 如果分不到东西，至少返回整篇
    if not chunks and text:
        chunks = [text]

    return chunks
