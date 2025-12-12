# -*- coding: utf-8 -*-
# @File: infrastructure/rag/splitter.py
# @Author: yaccii
# @Description: 文本切分：段落 + 滑动窗口

from __future__ import annotations

from typing import List


def _coarse_paragraphs(text: str) -> List[str]:
    # 按空行或换行做粗切，去掉过短/空白段
    raw = [p.strip() for p in (text or "").replace("\r\n", "\n").split("\n\n")]
    paras: List[str] = []
    for p in raw:
        if not p:
            continue
        # 再细分一次，避免超长行
        subs = [s.strip() for s in p.split("\n")]
        for s in subs:
            if s:
                paras.append(s)
    return paras


def split_text(text: str, max_chars: int = 800, overlap: int = 200) -> List[str]:
    if not text:
        return []
    paras = _coarse_paragraphs(text)
    chunks: List[str] = []

    cur: List[str] = []
    cur_len = 0

    for para in paras:
        if cur_len + len(para) + 1 <= max_chars:
            cur.append(para)
            cur_len += len(para) + 1
        else:
            if cur:
                chunks.append("\n".join(cur))
            # 生成带重叠的新窗口
            if chunks and overlap > 0:
                tail = chunks[-1][-overlap:]
                cur = [tail, para] if tail else [para]
                cur_len = len(tail) + len(para)
            else:
                cur = [para]
                cur_len = len(para)

            # 如果单段就超长，强制切割
            while cur_len > max_chars and len(cur) == 1:
                s = cur[0]
                head = s[:max_chars]
                chunks.append(head)
                rem = s[max_chars - overlap :] if overlap > 0 else s[max_chars:]
                cur = [rem]
                cur_len = len(rem)

    if cur:
        chunks.append("\n".join(cur))

    return chunks or [text[:max_chars]]
