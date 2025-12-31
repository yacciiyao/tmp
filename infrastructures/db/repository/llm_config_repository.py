# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: LLM config repository (service DB). No business logic.

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.orm.llm_orm import LlmModelProfilesORM, LlmFlowPoliciesORM, LlmConfigVersionsORM


class LlmConfigRepository:
    # -----------------------------
    # Config versions
    # -----------------------------

    @staticmethod
    async def get_active_version(db: AsyncSession, *, scope: str = "global") -> Optional[LlmConfigVersionsORM]:
        stmt = (
            select(LlmConfigVersionsORM)
            .where(LlmConfigVersionsORM.scope == str(scope), LlmConfigVersionsORM.status == 1)
            .order_by(LlmConfigVersionsORM.version_id.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        return res.scalars().first()

    # -----------------------------
    # Model profiles
    # -----------------------------

    @staticmethod
    async def list_model_profiles(
        db: AsyncSession,
        *,
        enabled_only: bool = True,
        limit: int = 500,
        offset: int = 0,
    ) -> List[LlmModelProfilesORM]:
        stmt = select(LlmModelProfilesORM)
        if enabled_only:
            stmt = stmt.where(LlmModelProfilesORM.is_enabled == 1)
        stmt = stmt.order_by(LlmModelProfilesORM.profile_id.asc()).offset(int(offset)).limit(int(limit))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_model_profile(db: AsyncSession, *, profile_id: str) -> Optional[LlmModelProfilesORM]:
        stmt = select(LlmModelProfilesORM).where(LlmModelProfilesORM.profile_id == str(profile_id))
        res = await db.execute(stmt)
        return res.scalars().first()

    # -----------------------------
    # Flow policies
    # -----------------------------

    @staticmethod
    async def list_flow_policies(
        db: AsyncSession,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> List[LlmFlowPoliciesORM]:
        stmt = select(LlmFlowPoliciesORM).order_by(LlmFlowPoliciesORM.flow_code.asc()).offset(int(offset)).limit(int(limit))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_flow_policy(db: AsyncSession, *, flow_code: str) -> Optional[LlmFlowPoliciesORM]:
        stmt = select(LlmFlowPoliciesORM).where(LlmFlowPoliciesORM.flow_code == str(flow_code))
        res = await db.execute(stmt)
        return res.scalars().first()
