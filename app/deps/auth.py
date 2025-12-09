# -*- coding: utf-8 -*-
# @File: auth.py
# @Author: yaccii
# @Description:
# app/deps/auth.py
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from application.auth.auth_service import AuthService
from application.common.errors import AppError
from domain.user import UserRole
from infrastructure.db.deps import get_db
from infrastructure.db.models.user_orm import UserORM
from infrastructure.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_auth_service = AuthService()
_user_repo = UserRepository()


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> UserORM:
    """
    从 Authorization: Bearer <token> 中解析当前用户。
    """
    payload = _auth_service.decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise AppError(
            code="auth.invalid_token",
            message="Token payload missing subject",
            http_status=401,
        )

    try:
        user_id = int(sub)
    except ValueError:
        raise AppError(
            code="auth.invalid_token",
            message="Token subject is invalid",
            http_status=401,
        )

    user = await _user_repo.get_by_id(db, user_id)
    if not user or not user.is_active:
        raise AppError(
            code="auth.user_not_found",
            message="User not found or inactive",
            http_status=401,
        )

    return user


async def get_current_admin(
    current_user: Annotated[UserORM, Depends(get_current_user)],
) -> UserORM:
    """
    仅 admin 可访问的依赖。
    """
    if current_user.role != UserRole.ADMIN.value:
        raise AppError(
            code="auth.not_admin",
            message="Admin privileges required",
            http_status=403,
        )
    return current_user
