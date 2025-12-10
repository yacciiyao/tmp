# -*- coding: utf-8 -*-
# @File: app/routers/model_router.py
# @Author: yaccii
# @Description: LLM 模型管理接口（增删改查）

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.model.dto import LLMModelCreate, LLMModelOut, LLMModelUpdate
from application.model.model_service import LLMModelService
from infrastructure.db.deps import get_db
from app.deps.auth import get_current_user, get_current_admin
from domain.user import UserPublic

router = APIRouter(prefix="/models", tags=["models"])


# ---------- 列表 ----------

@router.get("", response_model=List[LLMModelOut])
async def list_models(
    enabled: Optional[bool] = None,
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_user),
):
    """
    查询模型列表：
    - enabled: 过滤是否启用
    - provider: 过滤 provider（openai / deepseek / qwen / ...）
    """
    service = LLMModelService(db)
    return await service.list_models(enabled=enabled, provider=provider)


# ---------- 详情 ----------

@router.get("/{alias}", response_model=LLMModelOut)
async def get_model(
    alias: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_user),
):
    service = LLMModelService(db)
    return await service.get_model(alias)


# ---------- 新增 ----------

@router.post("", response_model=LLMModelOut)
async def create_model(
    data: LLMModelCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: UserPublic = Depends(get_current_admin),
):
    service = LLMModelService(db)
    return await service.create_model(data)


# ---------- 更新 ----------

@router.patch("/{alias}", response_model=LLMModelOut)
async def update_model(
    alias: str,
    data: LLMModelUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: UserPublic = Depends(get_current_admin),
):
    service = LLMModelService(db)
    return await service.update_model(alias, data)


# ---------- 删除（软删） ----------

@router.delete("/{alias}")
async def delete_model(
    alias: str,
    db: AsyncSession = Depends(get_db),
    current_admin: UserPublic = Depends(get_current_admin),
):
    service = LLMModelService(db)
    await service.delete_model(alias)
    return {"success": True}


# ---------- 设置默认模型 ----------

@router.post("/{alias}/default", response_model=LLMModelOut)
async def set_default_model(
    alias: str,
    db: AsyncSession = Depends(get_db),
    current_admin: UserPublic = Depends(get_current_admin),
):
    service = LLMModelService(db)
    return await service.set_default(alias)
