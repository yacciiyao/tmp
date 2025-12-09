# -*- coding: utf-8 -*-
# @File: infrastructure/db/models/chat_orm.py
# @Author: yaccii
# @Description: Chat / Session ORM

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.base import Base, TimestampMixin, now_ts

# 会话状态：
# 0 = deleted（逻辑删除）
# 1 = active
# 2 = archived


class ChatSessionORM(TimestampMixin, Base):
    __tablename__ = "chat_session"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)

    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_alias: Mapped[str] = mapped_column(String(64), nullable=False)

    use_rag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rag_corpus_ids_json: Mapped[Optional[str]] = mapped_column(
        "rag_corpus_ids",
        Text,
        nullable=True,
    )

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,  # active
    )
    last_message_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    meta_json: Mapped[Optional[str]] = mapped_column("meta", Text, nullable=True)

    messages: Mapped[List["ChatMessageORM"]] = relationship(
        "ChatMessageORM",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    summaries: Mapped[List["ChatSessionSummaryORM"]] = relationship(
        "ChatSessionSummaryORM",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    @property
    def rag_corpus_ids(self) -> List[int]:
        if not self.rag_corpus_ids_json:
            return []
        try:
            return json.loads(self.rag_corpus_ids_json)
        except Exception:
            return []

    @rag_corpus_ids.setter
    def rag_corpus_ids(self, value: List[int]) -> None:
        self.rag_corpus_ids_json = json.dumps(value or [], ensure_ascii=False)

    @property
    def meta(self) -> Optional[Dict[str, Any]]:
        if not self.meta_json:
            return None
        try:
            return json.loads(self.meta_json)
        except Exception:
            return None

    @meta.setter
    def meta(self, value: Optional[Dict[str, Any]]) -> None:
        self.meta_json = json.dumps(value or {}, ensure_ascii=False)


class ChatMessageORM(TimestampMixin, Base):
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_session.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    role: Mapped[str] = mapped_column(String(16), nullable=False)
    message_type: Mapped[str] = mapped_column(String(16), nullable=False, default="text")

    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reply_to_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    parsed_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsed_meta_json: Mapped[Optional[str]] = mapped_column("parsed_meta", Text, nullable=True)

    audit_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    session: Mapped[ChatSessionORM] = relationship("ChatSessionORM", back_populates="messages")

    attachments: Mapped[List["ChatAttachmentORM"]] = relationship(
        "ChatAttachmentORM",
        back_populates="message",
        cascade="all, delete-orphan",
    )

    @property
    def parsed_meta(self) -> Optional[Dict[str, Any]]:
        if not self.parsed_meta_json:
            return None
        try:
            return json.loads(self.parsed_meta_json)
        except Exception:
            return None

    @parsed_meta.setter
    def parsed_meta(self, value: Optional[Dict[str, Any]]) -> None:
        self.parsed_meta_json = json.dumps(value or {}, ensure_ascii=False)


class ChatAttachmentORM(TimestampMixin, Base):
    __tablename__ = "chat_attachment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chat_message.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    extra_meta_json: Mapped[Optional[str]] = mapped_column("extra_meta", Text, nullable=True)

    message: Mapped[ChatMessageORM] = relationship("ChatMessageORM", back_populates="attachments")

    @property
    def extra_meta(self) -> Optional[Dict[str, Any]]:
        if not self.extra_meta_json:
            return None
        try:
            return json.loads(self.extra_meta_json)
        except Exception:
            return None

    @extra_meta.setter
    def extra_meta(self, value: Optional[Dict[str, Any]]) -> None:
        self.extra_meta_json = json.dumps(value or {}, ensure_ascii=False)


class ChatSessionSummaryORM(TimestampMixin, Base):
    __tablename__ = "chat_session_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_session.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    summary_type: Mapped[str] = mapped_column(String(16), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)

    meta_json: Mapped[Optional[str]] = mapped_column("meta", Text, nullable=True)

    session: Mapped[ChatSessionORM] = relationship("ChatSessionORM", back_populates="summaries")

    @property
    def meta(self) -> Optional[Dict[str, Any]]:
        if not self.meta_json:
            return None
        try:
            return json.loads(self.meta_json)
        except Exception:
            return None

    @meta.setter
    def meta(self, value: Optional[Dict[str, Any]]) -> None:
        self.meta_json = json.dumps(value or {}, ensure_ascii=False)
