# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user
from infrastructures.db.orm.orm_deps import get_db
from infrastructures.db.orm.user_orm import MetaUsersORM
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

_auth_service = AuthService()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    user_id: int
    username: str
    role: str
    status: int


@router.post("/login", response_model=TokenResponse)
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await _auth_service.authenticate_or_raise(
        db=db,
        username=form_data.username,
        password=form_data.password,
    )

    token = _auth_service.create_access_token_for_user(user)
    return TokenResponse(access_token=token)


class LoginJSONRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.post("/login-json", response_model=TokenResponse)
async def login_json(
        body: LoginJSONRequest,
        db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await _auth_service.authenticate_or_raise(
        db=db,
        username=body.username,
        password=body.password,
    )

    token = _auth_service.create_access_token_for_user(user)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def get_me(
        current_user: Annotated[MetaUsersORM, Depends(get_current_user)],
) -> MeResponse:
    return MeResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        role=current_user.role,
        status=current_user.status,
    )
