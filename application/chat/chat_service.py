from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional, cast

from sqlalchemy.ext.asyncio import AsyncSession

from domain.chat import ChatMessage, ChatSession
from infrastructure import mlogger
from infrastructure.llm.llm_registry import LLMRegistry
from infrastructure.repositories.chat_repository import ChatRepository


class ChatService:
    """
    Chat 服务：会话管理 / 非流式对话 / 流式对话。
    说明：
    - 已移除对 RAGQueryService 的依赖。_prepare_rag 目前做安全降级（占位返回），
      等你提供新的内部检索接口后，可在该方法内接入真实 RAG。
    """

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

    async def update_session_if_empty(
        self,
        *,
        session_id: str,
        user_id: int,
        model_alias: Optional[str] = None,
        use_rag: Optional[bool] = None,
        rag_corpus_ids: Optional[List[int]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> ChatSession:
        """
        仅当会话没有任何消息时允许修改配置；否则抛 RuntimeError('session_not_empty')
        """
        session = await self.repo.get_session(session_id=session_id, user_id=user_id)
        if not session:
            raise ValueError("Session not found")

        msgs = await self.repo.list_messages(session_id=session.id, limit=1)
        if msgs:
            raise RuntimeError("session_not_empty")

        changed = False
        if model_alias is not None and model_alias != session.model_alias:
            session.model_alias = model_alias
            changed = True
        if use_rag is not None and use_rag != session.use_rag:
            session.use_rag = use_rag
            changed = True
        if rag_corpus_ids is not None:
            session.rag_corpus_ids = rag_corpus_ids
            changed = True
        if meta is not None:
            session.meta = meta
            changed = True

        if changed:
            await self.db.flush()
            await self.db.commit()
        return session

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

        # 1) 先落地用户消息
        user_msg = await self.repo.create_message(
            session_id=session.id,
            user_id=user_id,
            role="user",
            message_type=message_type,
            content_text=content_text,
        )

        # 2) 最近历史
        history = await self.repo.list_messages(session_id=session.id, limit=20)

        # 3) RAG（占位：未实际检索，返回 used=False）
        rag_used, rag_context, rag_debug = await self._prepare_rag(
            session=session,
            user_input=content_text,
        )

        # 4) 组装 LLM 消息
        messages = self._build_llm_messages(
            session=session,
            history=history,
            user_input=content_text,
            rag_context=rag_context if rag_used else None,
        )

        # 5) 调模型
        client = await self.llm_registry.get_client(session.model_alias)
        client = cast(Any, client)
        answer_text = await client.acomplete(messages)

        # 6) 写入 assistant 消息
        assistant_msg = await self.repo.create_message(
            session_id=session.id,
            user_id=None,
            role="assistant",
            message_type="text",
            content_text=answer_text,
            parsed_meta={"rag": rag_debug} if rag_used else None,
        )

        # 7) 自动补标题
        session = await self._ensure_session_title(
            session=session,
            first_user_message=content_text,
        )

        await self.db.commit()

        return {
            "session": session,
            "request_message": user_msg,
            "answer_message": assistant_msg,
            "used_rag": rag_used,
            "extra": {"rag": rag_debug} if rag_used else {},
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

        # 1) 用户消息
        await self.repo.create_message(
            session_id=session.id,
            user_id=user_id,
            role="user",
            message_type=message_type,
            content_text=content_text,
        )

        # 2) 历史
        history = await self.repo.list_messages(session_id=session.id, limit=20)

        # 3) RAG（占位）
        rag_used, rag_context, rag_debug = await self._prepare_rag(
            session=session,
            user_input=content_text,
        )

        # 4) LLM 消息
        messages = self._build_llm_messages(
            session=session,
            history=history,
            user_input=content_text,
            rag_context=rag_context if rag_used else None,
        )

        client = await self.llm_registry.get_client(session.model_alias)
        client = cast(Any, client)

        chunks: List[str] = []
        try:
            async for chunk in client.astream(messages):
                if not chunk:
                    continue
                chunks.append(chunk)
                yield chunk
        finally:
            full_answer = "".join(chunks).strip()
            if full_answer:
                await self.repo.create_message(
                    session_id=session.id,
                    user_id=None,
                    role="assistant",
                    message_type="text",
                    content_text=full_answer,
                    parsed_meta={"rag": rag_debug} if rag_used else None,
                )
                await self._ensure_session_title(
                    session=session,
                    first_user_message=content_text,
                )
                await self.db.commit()

    # ------------------------ 消息列表 ------------------------

    async def list_messages(
        self,
        *,
        session_id: str,
        user_id: int,
        limit: int = 500,
        offset: int = 0,
    ) -> List[ChatMessage]:
        session = await self.repo.get_session(session_id=session_id, user_id=user_id)
        if not session:
            raise ValueError("Session not found")
        return await self.repo.list_messages(session_id=session.id, limit=limit, offset=offset)

    # ------------------------ 内部工具：RAG（占位实现） ------------------------

    async def _prepare_rag(
        self,
        *,
        session: ChatSession,
        user_input: str,
    ) -> tuple[bool, str, Dict[str, Any]]:
        """
        占位实现：
        - 保留接口与返回结构，暂不做实际检索。
        - 当你提供新的检索入口（例如 RAGEngine.query(corpus_id, query, ...)），
          在此处按会话的 rag_corpus_ids 聚合结果并返回上下文文本。
        """
        # 若未开启 RAG 或无 corpus，直接关闭
        if not session.use_rag:
            return False, "", {}
        if not session.rag_corpus_ids:
            return False, "", {}

        debug = {
            "used": False,
            "total_hits": 0,
            "corpora": [
                {"corpus_id": cid, "hit_count": 0, "context_preview": ""}
                for cid in (session.rag_corpus_ids or [])
            ],
            "hits": [],
        }
        return False, "", debug

    # ------------------------ 内部工具：消息构造 ------------------------

    @staticmethod
    def _build_llm_messages(
        *,
        session: ChatSession,
        history: List[ChatMessage],
        user_input: str,
        rag_context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []

        if rag_context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "你是企业内部知识库问答助手。"
                        "下面是根据用户问题检索到的相关知识库内容，请优先参考这些内容回答。"
                        "如果内容与问题无关，可以忽略，并明确说明依据不足：\n\n"
                        f"{rag_context}"
                    ),
                }
            )

        for msg in history:
            if msg.role not in ("user", "assistant"):
                continue
            if not msg.content_text:
                continue
            messages.append({"role": msg.role, "content": msg.content_text})

        messages.append({"role": "user", "content": user_input})
        return messages

    # ------------------------ 内部工具：自动标题 ------------------------

    async def _ensure_session_title(
        self,
        *,
        session: ChatSession,
        first_user_message: str,
    ) -> ChatSession:
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
            {"role": "user", "content": first_user_message},
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
