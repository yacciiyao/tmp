# -*- coding: utf-8 -*-
# @File: app/routers/chat_router.py
# @Author: yaccii
# @Description: Chat / Session HTTP API

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from application.chat.chat_service import ChatService
from domain.user import User
from infrastructure.db.deps import get_db
from app.deps.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


# ===================== Schemas =====================

class SessionCreateRequest(BaseModel):
    model_alias: str = Field(..., description="会话绑定的模型 alias")
    use_rag: bool = Field(False, description="是否启用 RAG 检索")
    rag_corpus_ids: Optional[List[int]] = Field(
        default=None,
        description="绑定的 RAG 知识库 ID 列表",
    )
    meta: Optional[Dict[str, Any]] = Field(
        default=None,
        description="会话扩展信息（预留 agent_mode 等）",
    )

class SessionPatchRequest(BaseModel):
    model_alias: Optional[str] = None
    use_rag: Optional[bool] = None
    rag_corpus_ids: Optional[List[int]] = None
    meta: Optional[Dict[str, Any]] = None


class SessionResponse(BaseModel):
    id: str                     # UUID
    user_id: int
    title: Optional[str]
    model_alias: str
    use_rag: bool
    rag_corpus_ids: List[int]
    status: int                 # 0=deleted,1=active,2=archived（返回时一般不会是0）
    last_message_at: Optional[int]
    meta: Optional[Dict[str, Any]]
    created_at: Optional[int]
    updated_at: Optional[int]


class SessionListResponse(BaseModel):
    items: List[SessionResponse]
    total: int


class ChatRequest(BaseModel):
    content: str = Field(..., description="用户输入文本")
    message_type: str = Field("text", description="消息类型，目前主要是 text")


class ChatMessageResponse(BaseModel):
    id: int
    session_id: str
    user_id: Optional[int]
    role: str
    message_type: str
    content_text: Optional[str]
    reply_to_message_id: Optional[int]
    parsed_text: Optional[str]
    parsed_meta: Optional[Dict[str, Any]]
    audit_status: Optional[str]
    created_at: Optional[int]
    updated_at: Optional[int]


class ChatResultResponse(BaseModel):
    session: SessionResponse
    request_message: ChatMessageResponse
    answer_message: ChatMessageResponse
    used_rag: bool
    extra: Dict[str, Any] = Field(default_factory=dict)


# ===================== mapping =====================

def _session_to_schema(session) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        title=session.title,
        model_alias=session.model_alias,
        use_rag=session.use_rag,
        rag_corpus_ids=session.rag_corpus_ids or [],
        status=session.status,
        last_message_at=session.last_message_at,
        meta=session.meta,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _message_to_schema(msg) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=msg.id,
        session_id=msg.session_id,
        user_id=msg.user_id,
        role=msg.role,
        message_type=msg.message_type,
        content_text=msg.content_text,
        reply_to_message_id=msg.reply_to_message_id,
        parsed_text=msg.parsed_text,
        parsed_meta=msg.parsed_meta,
        audit_status=msg.audit_status,
        created_at=msg.created_at,
        updated_at=msg.updated_at,
    )


# ===================== Session APIs =====================

@router.post(
    "/sessions",
    response_model=SessionResponse,
    summary="创建会话",
)
async def create_session(
    body: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatService(db)
    session = await service.create_session(
        user_id=current_user.id,
        model_alias=body.model_alias,
        use_rag=body.use_rag,
        rag_corpus_ids=body.rag_corpus_ids or [],
        meta=body.meta,
    )
    return _session_to_schema(session)


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="会话列表",
)
async def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatService(db)
    sessions = await service.list_sessions(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return SessionListResponse(
        items=[_session_to_schema(s) for s in sessions],
        total=len(sessions),
    )


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="会话详情",
)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatService(db)
    session = await service.get_session(
        session_id=session_id,
        user_id=current_user.id,
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return _session_to_schema(session)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除会话（逻辑删除）",
)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatService(db)
    ok = await service.delete_session(
        session_id=session_id,
        user_id=current_user.id,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="更新会话配置（仅空会话）",
)
async def patch_session(
    session_id: str,
    body: SessionPatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatService(db)
    try:
        session = await service.update_session_if_empty(
            session_id=session_id,
            user_id=current_user.id,
            model_alias=body.model_alias,
            use_rag=body.use_rag,
            rag_corpus_ids=body.rag_corpus_ids,
            meta=body.meta,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden")
    except RuntimeError as e:
        # 非空会话不允许修改
        raise HTTPException(status_code=409, detail=str(e))

    return _session_to_schema(session)


# ===================== Chat APIs =====================

@router.get(
    "/sessions/{session_id}/messages",
    response_model=List[ChatMessageResponse],
    summary="消息列表",
)
async def list_messages_api(
    session_id: str,
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatService(db)
    try:
        msgs = await service.list_messages(
            session_id=session_id,
            user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return [_message_to_schema(m) for m in msgs]


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatResultResponse,
    summary="非流式对话",
)
async def chat_completion(
    session_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatService(db)
    try:
        result = await service.chat(
            session_id=session_id,
            user_id=current_user.id,
            content_text=body.content,
            message_type=body.message_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    session = _session_to_schema(result["session"])
    req_msg = _message_to_schema(result["request_message"])
    ans_msg = _message_to_schema(result["answer_message"])

    return ChatResultResponse(
        session=session,
        request_message=req_msg,
        answer_message=ans_msg,
        used_rag=bool(result.get("used_rag")),
        extra=result.get("extra") or {},
    )


@router.get(
    "/sessions/{session_id}/stream",
    summary="流式对话（SSE）",
)
async def chat_stream(
    session_id: str,
    content: str = Query(..., description="用户输入文本"),
    message_type: str = Query("text", description="消息类型"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatService(db)

    async def event_generator():
        try:
            async for chunk in service.chat_stream(
                session_id=session_id,
                user_id=current_user.id,
                content_text=content,
                message_type=message_type,
            ):
                if not chunk:
                    continue
                yield f"data: {chunk}\n\n"
            yield "event: end\ndata: [DONE]\n\n"
        except ValueError as e:
            yield f"event: error\ndata: {str(e)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
