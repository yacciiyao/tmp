# -*- coding: utf-8 -*-
# @File: auth_router.py
# @Author: yaccii
# @Description:
# app/routers/auth_router.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from application.auth.auth_service import AuthService
from application.common.errors import AppError
from app.deps.auth import get_current_user
from infrastructure.db.deps import get_db
from infrastructure.db.models.user_orm import UserORM

router = APIRouter(prefix="/api/auth", tags=["auth"])

_auth_service = AuthService()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await _auth_service.authenticate(db, body.username, body.password)
    if not user:
        raise AppError(
            code="auth.invalid_credentials",
            message="Invalid username or password",
            http_status=401,
        )

    token = _auth_service.create_access_token_for_user(user)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: Annotated[UserORM, Depends(get_current_user)],
):
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        is_active=current_user.is_active,
    )
