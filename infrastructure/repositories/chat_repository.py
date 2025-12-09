# -*- coding: utf-8 -*-
# @File: infrastructure/repositories/chat_repository.py
# @Author: yaccii
# @Description: Chat / Session Repository

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.chat import (
    ChatAttachment,
    ChatMessage,
    ChatSession,
    ChatSessionSummary,
)
from infrastructure.db.base import now_ts
from infrastructure.db.models.chat_orm import (
    ChatAttachmentORM,
    ChatMessageORM,
    ChatSessionORM,
    ChatSessionSummaryORM,
)

# 状态：0=deleted, 1=active, 2=archived


def _session_from_orm(orm: ChatSessionORM) -> ChatSession:
    return ChatSession(
        id=orm.id,
        user_id=orm.user_id,
        title=orm.title,
        model_alias=orm.model_alias,
        use_rag=orm.use_rag,
        rag_corpus_ids=orm.rag_corpus_ids,
        status=orm.status,
        last_message_at=orm.last_message_at,
        meta=orm.meta,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _message_from_orm(orm: ChatMessageORM) -> ChatMessage:
    return ChatMessage(
        id=orm.id,
        session_id=orm.session_id,
        user_id=orm.user_id,
        role=orm.role,
        message_type=orm.message_type,
        content_text=orm.content_text,
        reply_to_message_id=orm.reply_to_message_id,
        parsed_text=orm.parsed_text,
        parsed_meta=orm.parsed_meta,
        audit_status=orm.audit_status,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _attachment_from_orm(orm: ChatAttachmentORM) -> ChatAttachment:
    return ChatAttachment(
        id=orm.id,
        message_id=orm.message_id,
        file_path=orm.file_path,
        file_url=orm.file_url,
        file_name=orm.file_name,
        mime_type=orm.mime_type,
        size_bytes=orm.size_bytes,
        extra_meta=orm.extra_meta,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _summary_from_orm(orm: ChatSessionSummaryORM) -> ChatSessionSummary:
    return ChatSessionSummary(
        id=orm.id,
        session_id=orm.session_id,
        summary_type=orm.summary_type,
        summary_text=orm.summary_text,
        meta=json.loads(orm.meta_json) if orm.meta_json else None,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


class ChatRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------ Session ------------------------

    async def create_session(
        self,
        *,
        user_id: int,
        model_alias: str,
        use_rag: bool,
        rag_corpus_ids: List[int],
        meta: Optional[Dict[str, Any]],
    ) -> ChatSession:
        ts = now_ts()
        orm = ChatSessionORM(
            user_id=user_id,
            title=None,
            model_alias=model_alias,
            use_rag=use_rag,
            status=1,  # active
            last_message_at=None,
        )
        orm.rag_corpus_ids = rag_corpus_ids or []
        orm.meta = meta or {}

        orm.created_at = ts
        orm.updated_at = ts

        self.db.add(orm)
        await self.db.flush()
        await self.db.refresh(orm)
        return _session_from_orm(orm)

    async def get_session(self, *, session_id: str, user_id: int) -> Optional[ChatSession]:
        stmt: Select = (
            select(ChatSessionORM)
            .where(
                ChatSessionORM.id == session_id,
                ChatSessionORM.user_id == user_id,
                ChatSessionORM.status != 0,  # 非 deleted
            )
            .limit(1)
        )
        res = await self.db.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        return _session_from_orm(orm)

    async def list_sessions(
        self,
        *,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ChatSession]:
        stmt: Select = (
            select(ChatSessionORM)
            .where(
                ChatSessionORM.user_id == user_id,
                ChatSessionORM.status != 0,
            )
            .order_by(
                desc(ChatSessionORM.last_message_at),
                desc(ChatSessionORM.created_at),
            )
            .offset(offset)
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        items = res.scalars().all()
        return [_session_from_orm(o) for o in items]

    async def update_session_title(
        self,
        *,
        session_id: str,
        user_id: int,
        title: str,
    ) -> Optional[ChatSession]:
        stmt: Select = (
            select(ChatSessionORM)
            .where(
                ChatSessionORM.id == session_id,
                ChatSessionORM.user_id == user_id,
                ChatSessionORM.status != 0,
            )
            .limit(1)
        )
        res = await self.db.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        orm.title = title
        orm.updated_at = now_ts()
        await self.db.flush()
        await self.db.refresh(orm)
        return _session_from_orm(orm)

    async def soft_delete_session(
        self,
        *,
        session_id: str,
        user_id: int,
    ) -> bool:
        """
        逻辑删除：status = 0，不级联删除消息。
        """
        stmt: Select = (
            select(ChatSessionORM)
            .where(
                ChatSessionORM.id == session_id,
                ChatSessionORM.user_id == user_id,
                ChatSessionORM.status != 0,
            )
            .limit(1)
        )
        res = await self.db.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return False
        orm.status = 0
        orm.updated_at = now_ts()
        await self.db.flush()
        return True

    # ------------------------ Message ------------------------

    async def create_message(
        self,
        *,
        session_id: str,
        user_id: Optional[int],
        role: str,
        message_type: str,
        content_text: Optional[str],
        reply_to_message_id: Optional[int] = None,
        parsed_text: Optional[str] = None,
        parsed_meta: Optional[Dict[str, Any]] = None,
        audit_status: Optional[str] = None,
    ) -> ChatMessage:
        ts = now_ts()
        orm = ChatMessageORM(
            session_id=session_id,
            user_id=user_id,
            role=role,
            message_type=message_type,
            content_text=content_text,
            reply_to_message_id=reply_to_message_id,
            parsed_text=parsed_text,
            audit_status=audit_status,
        )
        orm.parsed_meta = parsed_meta or {}
        orm.created_at = ts
        orm.updated_at = ts

        self.db.add(orm)

        # 更新会话最后消息时间（跳过已删除会话）
        session_orm = await self.db.get(ChatSessionORM, session_id)
        if session_orm and session_orm.status != 0:
            session_orm.last_message_at = ts
            session_orm.updated_at = ts

        await self.db.flush()
        await self.db.refresh(orm)
        return _message_from_orm(orm)

    async def list_messages(
        self,
        *,
        session_id: str,
        limit: int = 50,
    ) -> List[ChatMessage]:
        stmt: Select = (
            select(ChatMessageORM)
            .where(ChatMessageORM.session_id == session_id)
            .order_by(desc(ChatMessageORM.id))
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        items = list(res.scalars().all())
        items.reverse()
        return [_message_from_orm(o) for o in items]

    # ------------------------ Summary（预留） ------------------------

    async def create_summary(
        self,
        *,
        session_id: str,
        summary_type: str,
        summary_text: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> ChatSessionSummary:
        ts = now_ts()
        orm = ChatSessionSummaryORM(
            session_id=session_id,
            summary_type=summary_type,
            summary_text=summary_text,
            meta_json=json.dumps(meta or {}, ensure_ascii=False),
        )
        orm.created_at = ts
        orm.updated_at = ts

        self.db.add(orm)
        await self.db.flush()
        await self.db.refresh(orm)
        return _summary_from_orm(orm)
