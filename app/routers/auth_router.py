# -*- coding: utf-8 -*-
# @File: auth_router.py
# @Author: yaccii
# @Description:
# app/routers/auth_router.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from application.auth.auth_service import AuthService
from application.common.errors import AppError
from app.deps.auth import get_current_user
from infrastructure.db.deps import get_db
from infrastructure.db.models.user_orm import UserORM

router = APIRouter(prefix="/auth", tags=["auth"])

_auth_service = AuthService()


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
    # 这里使用 OAuth2PasswordRequestForm，以兼容 Swagger /docs 的 Authorize（password flow）
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    登录接口（OAuth2 password flow）：

    - /docs 里的 Authorize 会向 /api/auth/login 发送 x-www-form-urlencoded：
      grant_type=password&username=...&password=...&scope=&client_id=&client_secret=
    - 这里用 OAuth2PasswordRequestForm 来接收 username/password 等字段。
    """
    user = await _auth_service.authenticate(
        db=db,
        username=form_data.username,
        password=form_data.password,
    )
    if not user:
        raise AppError(
            code="auth.invalid_credentials",
            message="Invalid username or password",
            http_status=401,
        )

    token = _auth_service.create_access_token_for_user(user)
    return TokenResponse(access_token=token)

class LoginJSONRequest(BaseModel):
    username: str
    password: str


@router.post("/login-json", response_model=TokenResponse)
async def login_json(
    body: LoginJSONRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await _auth_service.authenticate(
        db=db,
        username=body.username,
        password=body.password,
    )
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
