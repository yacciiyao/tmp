# -*- coding: utf-8 -*-
# @File: domain/chat.py
# @Author: yaccii
# @Description: Chat / Session Domain Models

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# 会话状态：0 = deleted（逻辑删除）, 1 = active, 2 = archived


@dataclass
class ChatSession:
    id: str
    user_id: int

    title: Optional[str]
    model_alias: str

    use_rag: bool
    rag_corpus_ids: List[int]

    status: int = 1              # 1=active
    last_message_at: Optional[int] = None

    meta: Optional[Dict[str, Any]] = None

    created_at: Optional[int] = None
    updated_at: Optional[int] = None


@dataclass
class ChatMessage:
    id: int
    session_id: str
    user_id: Optional[int]

    role: str                    # user / assistant / system / tool
    message_type: str            # text / image / audio / video / file / ...

    content_text: Optional[str]

    reply_to_message_id: Optional[int] = None

    parsed_text: Optional[str] = None
    parsed_meta: Optional[Dict[str, Any]] = None

    audit_status: Optional[str] = None

    created_at: Optional[int] = None
    updated_at: Optional[int] = None


@dataclass
class ChatAttachment:
    id: int
    message_id: int

    file_path: str
    file_url: Optional[str]

    file_name: Optional[str]
    mime_type: Optional[str]
    size_bytes: Optional[int]

    extra_meta: Optional[Dict[str, Any]] = None

    created_at: Optional[int] = None
    updated_at: Optional[int] = None


@dataclass
class ChatSessionSummary:
    id: int
    session_id: str

    summary_type: str            # end / periodic / manual
    summary_text: str

    meta: Optional[Dict[str, Any]] = None

    created_at: Optional[int] = None
    updated_at: Optional[int] = None
