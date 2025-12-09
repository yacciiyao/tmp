# -*- coding: utf-8 -*-
# @File: application/chat/chat_service.py
# @Author: yaccii
# @Description: Chat / Session Service

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional, cast

from sqlalchemy.ext.asyncio import AsyncSession

from domain.chat import ChatMessage, ChatSession
from infrastructure import mlogger
from infrastructure.llm.llm_registry import LLMRegistry
from infrastructure.repositories.chat_repository import ChatRepository


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ChatRepository(db)
        self.llm_registry = LLMRegistry()

    # ------------------------ Session ------------------------

    async def create_session(
        self,
        *,
        user_id: int,
        model_alias: str,
        use_rag: bool,
        rag_corpus_ids: List[int],
        meta: Optional[Dict[str, Any]] = None,
    ) -> ChatSession:
        session = await self.repo.create_session(
            user_id=user_id,
            model_alias=model_alias,
            use_rag=use_rag,
            rag_corpus_ids=rag_corpus_ids,
            meta=meta,
        )
        await self.db.commit()
        return session

    async def get_session(self, *, session_id: str, user_id: int) -> Optional[ChatSession]:
        return await self.repo.get_session(session_id=session_id, user_id=user_id)

    async def list_sessions(
        self,
        *,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ChatSession]:
        return await self.repo.list_sessions(user_id=user_id, limit=limit, offset=offset)

    async def delete_session(self, *, session_id: str, user_id: int) -> bool:
        ok = await self.repo.soft_delete_session(session_id=session_id, user_id=user_id)
        if ok:
            await self.db.commit()
        return ok

    # ------------------------ Chat（非流式） ------------------------

    async def chat(
        self,
        *,
        session_id: str,
        user_id: int,
        content_text: str,
        message_type: str = "text",
    ) -> Dict[str, Any]:
        session = await self.repo.get_session(session_id=session_id, user_id=user_id)
        if not session:
            raise ValueError("Session not found")

        user_msg = await self.repo.create_message(
            session_id=session.id,
            user_id=user_id,
            role="user",
            message_type=message_type,
            content_text=content_text,
        )

        history = await self.repo.list_messages(session_id=session.id, limit=20)

        messages = self._build_llm_messages(
            session=session,
            history=history,
            user_input=content_text,
        )

        # 把 client 当成集成边界，显式 cast 成 Any，规避类型检查噪音
        client = await self.llm_registry.get_client(session.model_alias)
        client = cast(Any, client)

        answer_text = await client.acomplete(messages)

        assistant_msg = await self.repo.create_message(
            session_id=session.id,
            user_id=None,
            role="assistant",
            message_type="text",
            content_text=answer_text,
        )

        session = await self._ensure_session_title(
            session=session,
            first_user_message=content_text,
        )

        await self.db.commit()

        return {
            "session": session,
            "request_message": user_msg,
            "answer_message": assistant_msg,
            "used_rag": False,
            "extra": {},
        }

    # ------------------------ Chat（流式） ------------------------

    async def chat_stream(
        self,
        *,
        session_id: str,
        user_id: int,
        content_text: str,
        message_type: str = "text",
    ) -> AsyncIterator[str]:
        """
        真正的 async generator：
        - router 中可以直接 `async for chunk in service.chat_stream(...)`
        - 内部负责把最终答案写入 chat_message，并自动生成 title（一次性）
        """
        session = await self.repo.get_session(session_id=session_id, user_id=user_id)
        if not session:
            raise ValueError("Session not found")

        # 先落地用户消息
        await self.repo.create_message(
            session_id=session.id,
            user_id=user_id,
            role="user",
            message_type=message_type,
            content_text=content_text,
        )

        history = await self.repo.list_messages(session_id=session.id, limit=20)
        messages = self._build_llm_messages(
            session=session,
            history=history,
            user_input=content_text,
        )

        client = await self.llm_registry.get_client(session.model_alias)
        client = cast(Any, client)

        answer_chunks: List[str] = []

        try:
            async for chunk in client.astream(messages):
                if not chunk:
                    continue
                answer_chunks.append(chunk)
                yield chunk
        except Exception as e:
            mlogger.warning(
                "ChatService",
                "chat_stream",
                msg=f"stream error: {e}",
                session_id=session.id,
            )
            raise
        finally:
            full_answer = "".join(answer_chunks).strip()
            if full_answer:
                await self.repo.create_message(
                    session_id=session.id,
                    user_id=None,
                    role="assistant",
                    message_type="text",
                    content_text=full_answer,
                )
                await self._ensure_session_title(
                    session=session,
                    first_user_message=content_text,
                )
                await self.db.commit()

    # ------------------------ 内部工具 ------------------------

    @staticmethod
    def _build_llm_messages(
        *,
        session: ChatSession,
        history: List[ChatMessage],
        user_input: str,
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []

        for msg in history:
            if msg.role not in ("user", "assistant"):
                continue
            if not msg.content_text:
                continue
            messages.append(
                {
                    "role": msg.role,
                    "content": msg.content_text,
                }
            )

        messages.append({"role": "user", "content": user_input})
        return messages

    async def _ensure_session_title(
        self,
        *,
        session: ChatSession,
        first_user_message: str,
    ) -> ChatSession:
        """
        会话不带 title 时自动生成：
        - 只在 title 为空时触发
        - 生成逻辑走当前会话绑定的模型
        """
        if session.title:
            return session

        try:
            client = await self.llm_registry.get_client(session.model_alias)
            client = cast(Any, client)
        except Exception as e:
            mlogger.warning("ChatService", "ensure_title", msg=f"get_client error: {e}")
            return session

        prompt = [
            {
                "role": "system",
                "content": "你是会话命名助手，只输出一个不超过15个字的中文标题，不要带引号，不要解释。",
            },
            {
                "role": "user",
                "content": first_user_message,
            },
        ]

        try:
            title = (await client.acomplete(prompt)).strip()
        except Exception as e:
            mlogger.warning("ChatService", "ensure_title", msg=f"gen title error: {e}")
            return session

        if not title:
            return session

        updated = await self.repo.update_session_title(
            session_id=session.id,
            user_id=session.user_id,
            title=title,
        )
        return updated or session
