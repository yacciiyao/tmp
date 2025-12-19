# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from domains.error_domain import AppError
from domains.user_domain import UserRole
from infrastructures.db.orm.orm_deps import get_db
from infrastructures.db.orm.user_orm import UserORM
from services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> UserORM:
    if token is None or token.strip() == "":
        raise AppError(code="auth.missing_token", message="Missing bearer token", http_status=401)

    return await AuthService().get_user_by_token(db, token)


async def get_current_admin(
    current_user: Annotated[UserORM, Depends(get_current_user)],
) -> UserORM:
    if current_user.role != UserRole.admin.value:
        raise AppError(code="auth.not_admin", message="Admin privileges required", http_status=403)
    return current_user
