# -*- coding: utf-8 -*-
# @File: application/chat/dto.py
# @Author: yaccii
# @Description: Chat 相关 DTO

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict


MessageRole = Literal["user", "assistant", "system", "tool"]


# ====================== Session DTO ======================


class SessionCreateRequest(BaseModel):
    """
    创建会话请求：
    - user_id 暂时由前端传，后续可由鉴权层覆盖
    """
    user_id: int = 0
    title: Optional[str] = None
    model_alias: str

    use_rag: bool = False
    rag_corpus_ids: List[int] = []

    meta: Optional[Dict[str, Any]] = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int

    title: Optional[str]
    model_alias: str

    use_rag: bool
    rag_corpus_ids: List[int]

    status: str
    last_message_at: Optional[int]

    meta: Optional[Dict[str, Any]]

    created_at: Optional[int]
    updated_at: Optional[int]


class SessionListResponse(BaseModel):
    items: List[SessionResponse]


# ====================== Message / Chat DTO ======================


class ChatMessageCreateRequest(BaseModel):
    """
    发送消息请求：
    - session_id: 会话 ID
    - user_id: 发送方用户 ID
    - content_text: 发送内容（文本）
    - message_type: text / image / audio / video / file / ...
    - reply_to_message_id: 引用消息
    - stream: 是否流式
    """
    session_id: int
    user_id: Optional[int] = 0

    content_text: str
    message_type: str = "text"

    reply_to_message_id: Optional[int] = None

    stream: bool = False


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    user_id: Optional[int]

    role: MessageRole
    message_type: str

    content_text: Optional[str]

    reply_to_message_id: Optional[int]

    parsed_text: Optional[str]
    parsed_meta: Optional[Dict[str, Any]]

    audit_status: Optional[str]

    created_at: Optional[int]
    updated_at: Optional[int]


class ChatResponse(BaseModel):
    """
    非流式对话响应：
    - session: 当前会话
    - answer: 模型回复文本
    - message: 持久化后的 assistant 消息
    - rag_used: 是否启用了 RAG
    """
    session: SessionResponse
    answer: str
    message: ChatMessageResponse
    rag_used: bool = False
