from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional, cast

from sqlalchemy.ext.asyncio import AsyncSession

from application.rag.dto import RAGQueryRequest
from application.rag.query_service import RAGQueryService
from domain.chat import ChatMessage, ChatSession
from infrastructure import mlogger
from infrastructure.llm.llm_registry import LLMRegistry
from infrastructure.repositories.chat_repository import ChatRepository


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ChatRepository(db)
        self.llm_registry = LLMRegistry()
        # RAG 检索服务（仅 chat 内部使用）
        self.rag_query_service = RAGQueryService(db)

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

        # 1. 先落地用户消息
        user_msg = await self.repo.create_message(
            session_id=session.id,
            user_id=user_id,
            role="user",
            message_type=message_type,
            content_text=content_text,
        )

        # 2. 取最近历史
        history = await self.repo.list_messages(session_id=session.id, limit=20)

        # 3. RAG 检索（可选）
        rag_used, rag_context, rag_debug = await self._prepare_rag(
            session=session,
            user_input=content_text,
        )

        # 4. 组装 LLM 消息
        messages = self._build_llm_messages(
            session=session,
            history=history,
            user_input=content_text,
            rag_context=rag_context if rag_used else None,
        )

        # 5. 调模型
        client = await self.llm_registry.get_client(session.model_alias)
        client = cast(Any, client)

        answer_text = await client.acomplete(messages)

        # 6. 写入 assistant 消息（把 RAG 结果存到 parsed_meta）
        assistant_msg = await self.repo.create_message(
            session_id=session.id,
            user_id=None,
            role="assistant",
            message_type="text",
            content_text=answer_text,
            parsed_meta={"rag": rag_debug} if rag_used else None,
        )

        # 7. 自动补标题
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

        # 1. 先落地用户消息
        await self.repo.create_message(
            session_id=session.id,
            user_id=user_id,
            role="user",
            message_type=message_type,
            content_text=content_text,
        )

        # 2. 准备历史
        history = await self.repo.list_messages(session_id=session.id, limit=20)

        # 3. RAG 检索（可选）
        rag_used, rag_context, rag_debug = await self._prepare_rag(
            session=session,
            user_input=content_text,
        )

        # 4. 组装 LLM 消息
        messages = self._build_llm_messages(
            session=session,
            history=history,
            user_input=content_text,
            rag_context=rag_context if rag_used else None,
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
                # 把完整答案落库，并带上 RAG 调试信息
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

    # ------------------------ 内部工具：RAG ------------------------

    async def _prepare_rag(
        self,
        *,
        session: ChatSession,
        user_input: str,
    ) -> tuple[bool, str, Dict[str, Any]]:
        """
        根据会话配置决定是否走 RAG，并返回：
        - used: 是否真实使用了 RAG（有命中）
        - rag_context: 拼接好的上下文文本（给 LLM）
        - debug: 结构化调试信息（落 parsed_meta / extra）
        """
        # 基本开关判断
        if not session.use_rag:
            return False, "", {}

        corpus_ids = session.rag_corpus_ids or []
        if not corpus_ids:
            return False, "", {}

        user_input = (user_input or "").strip()
        if not user_input:
            return False, "", {}

        all_hits: List[Dict[str, Any]] = []
        corpus_items: List[Dict[str, Any]] = []
        context_parts: List[str] = []

        for corpus_id in corpus_ids:
            try:
                req = RAGQueryRequest(
                    corpus_id=corpus_id,
                    query=user_input,
                    top_k=8,
                    use_vector=True,
                    use_bm25=True,
                    use_rerank=False,
                )
                resp = await self.rag_query_service.query(req)
            except Exception as e:
                # 单个 corpus 失败视为降级，继续其他 corpus
                mlogger.warning(
                    "ChatService",
                    "rag_query",
                    msg=f"rag query error: {e!r}",
                    session_id=session.id,
                    corpus_id=corpus_id,
                )
                continue

            if not resp.hits:
                continue

            # 记录 corpus 级别信息
            preview = resp.context[:200] if resp.context else ""
            corpus_items.append(
                {
                    "corpus_id": resp.corpus_id,
                    "hit_count": len(resp.hits),
                    "context_preview": preview,
                }
            )
            if resp.context:
                context_parts.append(f"[知识库 {resp.corpus_id}]\n{resp.context}")

            # 展平 hits
            for rank, hit in enumerate(resp.hits, start=1):
                all_hits.append(
                    {
                        "corpus_id": hit.corpus_id,
                        "doc_id": hit.doc_id,
                        "chunk_id": hit.chunk_id,
                        "score": hit.score,
                        "source_type": hit.source_type,
                        "source_uri": hit.source_uri,
                        "text": hit.text,
                        "meta": hit.meta,
                        "rank_in_corpus": rank,
                    }
                )

        if not context_parts:
            # 没有任何有效命中，则视为未使用 RAG
            return False, "", {
                "used": False,
                "total_hits": 0,
                "corpora": corpus_items,
                "hits": [],
            }

        rag_context = "\n\n".join(context_parts)
        debug = {
            "used": True,
            "total_hits": len(all_hits),
            "corpora": corpus_items,
            "hits": all_hits,
        }
        return True, rag_context, debug

    # ------------------------ 内部工具：消息构造 ------------------------

    @staticmethod
    def _build_llm_messages(
        *,
        session: ChatSession,
        history: List[ChatMessage],
        user_input: str,
        rag_context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        根据历史 + 当前用户输入 + 可选 RAG 上下文构造发送给 LLM 的 messages。
        - history：只保留 user / assistant 且有 content_text 的消息
        - rag_context：存在时，插入一条 system 提示
        """
        messages: List[Dict[str, str]] = []

        # 如果有 RAG 上下文，插入 system 提示
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

        # 历史对话
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

        # 当前用户输入
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
