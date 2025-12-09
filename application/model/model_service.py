# -*- coding: utf-8 -*-
# @File: application/model/model_service.py
# @Author: yaccii
# @Description: LLM 模型管理 Service（增删改查）

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from application.common.errors import AppError
from application.model.dto import LLMModelCreate, LLMModelOut, LLMModelUpdate
from infrastructure.db.models.model_orm import LLMModelORM


class LLMModelService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---------- 查询 ----------

    async def list_models(
        self,
        *,
        enabled: Optional[bool] = None,
        provider: Optional[str] = None,
    ) -> List[LLMModelOut]:
        stmt = select(LLMModelORM)

        if enabled is not None:
            stmt = stmt.where(LLMModelORM.is_enabled == enabled)
        if provider:
            stmt = stmt.where(LLMModelORM.provider == provider)

        stmt = stmt.order_by(LLMModelORM.id.asc())

        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [LLMModelOut.model_validate(row) for row in rows]

    async def get_model(self, alias: str) -> LLMModelOut:
        stmt = select(LLMModelORM).where(LLMModelORM.alias == alias)
        result = await self.db.execute(stmt)
        orm = result.scalar_one_or_none()
        if not orm:
            raise AppError(
                code="llm.not_found",
                message=f"模型 {alias} 不存在",
                http_status=404,
            )
        return LLMModelOut.model_validate(orm)

    # ---------- 新增 ----------

    async def create_model(self, data: LLMModelCreate) -> LLMModelOut:
        # 1. alias 唯一性检查
        stmt = select(LLMModelORM.id).where(LLMModelORM.alias == data.alias)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise AppError(
                code="llm.alias_exists",
                message=f"模型 alias={data.alias} 已存在",
                http_status=400,
            )

        orm = LLMModelORM(**data.model_dump())
        self.db.add(orm)

        # 如果设置 is_default=True，需要清理其他默认
        if data.is_default:
            await self._clear_other_default(keep_alias=data.alias)

        await self.db.commit()
        await self.db.refresh(orm)
        return LLMModelOut.model_validate(orm)

    # ---------- 更新 ----------

    async def update_model(self, alias: str, data: LLMModelUpdate) -> LLMModelOut:
        stmt = select(LLMModelORM).where(LLMModelORM.alias == alias)
        result = await self.db.execute(stmt)
        orm = result.scalar_one_or_none()
        if not orm:
            raise AppError(
                code="llm.not_found",
                message=f"模型 {alias} 不存在",
                http_status=404,
            )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(orm, field, value)

        # 本次把 is_default 改为 True，则清理其他默认
        if update_data.get("is_default") is True:
            await self._clear_other_default(keep_alias=alias)

        await self.db.commit()
        await self.db.refresh(orm)
        return LLMModelOut.model_validate(orm)

    # ---------- 删除（软删） ----------

    async def delete_model(self, alias: str) -> None:
        """
        软删除：只是把 is_enabled 置为 False，不物理删记录。
        """
        stmt = (
            update(LLMModelORM)
            .where(LLMModelORM.alias == alias)
            .values(is_enabled=False)
        )
        result = await self.db.execute(stmt)
        # 某些驱动 rowcount 可能是 -1，这里只判断“没有匹配行”的情况
        if getattr(result, "rowcount", None) == 0:
            raise AppError(
                code="llm.not_found",
                message=f"模型 {alias} 不存在",
                http_status=404,
            )
        await self.db.commit()

    # ---------- 设置默认模型 ----------

    async def set_default(self, alias: str) -> LLMModelOut:
        """
        将指定 alias 设置为默认模型（全局唯一），其他全部 is_default=False。
        """
        stmt = select(LLMModelORM).where(LLMModelORM.alias == alias)
        result = await self.db.execute(stmt)
        orm = result.scalar_one_or_none()
        if not orm:
            raise AppError(
                code="llm.not_found",
                message=f"模型 {alias} 不存在",
                http_status=404,
            )

        # 清理其他默认
        await self._clear_other_default(keep_alias=alias)
        orm.is_default = True

        await self.db.commit()
        await self.db.refresh(orm)
        return LLMModelOut.model_validate(orm)

    # ---------- 内部工具方法 ----------

    async def _clear_other_default(self, keep_alias: str) -> None:
        """
        清理除 keep_alias 外的所有默认模型标记。
        不 commit，由调用方负责整体事务。
        """
        stmt = (
            update(LLMModelORM)
            .where(LLMModelORM.alias != keep_alias)
            .values(is_default=False)
        )
        await self.db.execute(stmt)
