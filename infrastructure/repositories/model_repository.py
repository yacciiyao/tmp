# -*- coding: utf-8 -*-
# @File: model_repository.py
# @Author: yaccii
# @Description:
# infrastructure/repositories/llm_model_repository.py
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.model import LLMModel, LLMModelCapabilities
from infrastructure.db.models.model_orm import LLMModelORM


class LLMModelRepository:
    """
    LLM 模型配置仓储：
    - 所有“系统里有哪些模型 & 各自能力”的真相都从这里读
    """

    @staticmethod
    def _to_domain(orm: LLMModelORM) -> LLMModel:
        caps = LLMModelCapabilities(
            chat=orm.support_chat,
            stream=orm.support_stream,
            embeddings=orm.support_embeddings,
            rerank=orm.support_rerank,
            vision=orm.support_vision,
            image=orm.support_image,
            audio_stt=orm.support_audio_stt,
            audio_tts=orm.support_audio_tts,
        )
        return LLMModel(
            id=orm.id,
            alias=orm.alias,
            name=orm.name,
            provider=orm.provider,
            endpoint_type=orm.endpoint_type,
            model_name=orm.model_name,
            source=orm.source,
            family=orm.family,
            base_url_env=orm.base_url_env,
            api_key_env=orm.api_key_env,
            capabilities=caps,
            max_input_tokens=orm.max_input_tokens,
            max_output_tokens=orm.max_output_tokens,
            is_default=orm.is_default,
            is_enabled=orm.is_enabled,
            remark=orm.remark,
        )

    # ---------- 通用模型查询 ----------

    async def get_by_alias(
        self,
        session: AsyncSession,
        alias: str,
        only_enabled: bool = True,
    ) -> Optional[LLMModel]:
        stmt = select(LLMModelORM).where(LLMModelORM.alias == alias)
        if only_enabled:
            stmt = stmt.where(LLMModelORM.is_enabled.is_(True))

        result = await session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return self._to_domain(orm)

    async def list_enabled(self, session: AsyncSession) -> List[LLMModel]:
        stmt = select(LLMModelORM).where(LLMModelORM.is_enabled.is_(True))
        result = await session.execute(stmt)
        orms = result.scalars().all()
        return [self._to_domain(o) for o in orms]

    # ---------- Embedding 模型相关 ----------

    async def list_embedding_models(self, session: AsyncSession) -> List[LLMModel]:
        """
        返回所有启用且支持 embeddings 的模型。
        """
        stmt = (
            select(LLMModelORM)
            .where(LLMModelORM.is_enabled.is_(True))
            .where(LLMModelORM.support_embeddings.is_(True))
        )
        result = await session.execute(stmt)
        orms = result.scalars().all()
        return [self._to_domain(o) for o in orms]

    async def get_default_embedding_model(self, session: AsyncSession) -> LLMModel:
        """
        获取“默认 embedding 模型”：
        - 先按 is_default=1 排序
        - 没有 is_default=1 时，取第一个支持 embedding 的启用模型
        """
        stmt = (
            select(LLMModelORM)
            .where(LLMModelORM.is_enabled.is_(True))
            .where(LLMModelORM.support_embeddings.is_(True))
            .order_by(LLMModelORM.is_default.desc(), LLMModelORM.id.asc())
        )
        result = await session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            raise ValueError("No enabled embedding LLM model configured in table 'llm_model'")
        return self._to_domain(orm)
