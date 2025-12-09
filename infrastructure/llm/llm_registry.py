# -*- coding: utf-8 -*-
# @File: llm_registry.py
# @Author: yaccii
# @Description:
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.base import AsyncSessionFactory
from infrastructure.db.models.model_orm import LLMModelORM

from .llm_base import BaseLLMClient, LLMCapabilities
from .openai_client import OpenAIClient
from .deepseek_client import DeepSeekClient
from .qwen_client import QwenClient
from .claude_client import ClaudeClient
from .gemini_client import GeminiClient
from .ollama_client import OllamaClient


@dataclass
class LLMModelConfig:
    """
    领域层的模型配置视图，来自 LLMModelORM。
    """
    id: int
    alias: str
    name: str
    provider: str
    endpoint_type: str
    model_name: str

    source: str
    family: Optional[str]

    base_url_env: Optional[str]
    api_key_env: Optional[str]

    support_chat: bool
    support_stream: bool
    support_embeddings: bool
    support_rerank: bool
    support_vision: bool
    support_image: bool
    support_audio_stt: bool
    support_audio_tts: bool

    max_input_tokens: Optional[int]
    max_output_tokens: Optional[int]

    is_default: bool
    is_enabled: bool
    remark: Optional[str]


class LLMRegistry:
    """
    LLM 统一注册中心 + 工厂：
    - 从 llm_model 表加载配置
    - 根据 endpoint_type/provider 构造具体 Client
    - 提供 get_client / get_default_xxx / list_enabled_models 等接口
    """

    def __init__(self) -> None:
        self._client_cache: Dict[str, BaseLLMClient] = {}

    # ---------- ORM -> Config ----------

    @staticmethod
    def _from_orm(row: LLMModelORM) -> LLMModelConfig:
        return LLMModelConfig(
            id=row.id,
            alias=row.alias,
            name=row.name,
            provider=row.provider,
            endpoint_type=row.endpoint_type,
            model_name=row.model_name,
            source=row.source,
            family=row.family,
            base_url_env=row.base_url_env,
            api_key_env=row.api_key_env,
            support_chat=row.support_chat,
            support_stream=row.support_stream,
            support_embeddings=row.support_embeddings,
            support_rerank=row.support_rerank,
            support_vision=row.support_vision,
            support_image=row.support_image,
            support_audio_stt=row.support_audio_stt,
            support_audio_tts=row.support_audio_tts,
            max_input_tokens=row.max_input_tokens,
            max_output_tokens=row.max_output_tokens,
            is_default=row.is_default,
            is_enabled=row.is_enabled,
            remark=row.remark,
        )

    @staticmethod
    def _capabilities_from_cfg(cfg: LLMModelConfig) -> LLMCapabilities:
        return LLMCapabilities(
            chat=cfg.support_chat,
            stream=cfg.support_stream,
            embeddings=cfg.support_embeddings,
            rerank=cfg.support_rerank,
            vision=cfg.support_vision,
            image=cfg.support_image,
            audio_stt=cfg.support_audio_stt,
            audio_tts=cfg.support_audio_tts,
        )

    async def _load_enabled_models(self, session: AsyncSession) -> List[LLMModelConfig]:
        stmt = select(LLMModelORM).where(LLMModelORM.is_enabled.is_(True))
        res = await session.execute(stmt)
        rows = res.scalars().all()
        return [self._from_orm(r) for r in rows]

    async def list_enabled_models(self) -> List[LLMModelConfig]:
        async with AsyncSessionFactory() as session:
            return await self._load_enabled_models(session)

    # ---------- env 解析 ----------

    @staticmethod
    def _resolve_credentials(cfg: LLMModelConfig) -> tuple[Optional[str], Optional[str]]:
        """
        根据 DB 中配置的 env 名获取 api_key/base_url，
        不在代码里写死任何 CLOSEAI/具体网关地址。
        """
        api_key = None
        base_url = None

        if cfg.api_key_env:
            api_key = os.getenv(cfg.api_key_env, None)

        if cfg.base_url_env:
            base_url = os.getenv(cfg.base_url_env, None)
            if base_url == "":
                base_url = None

        return api_key, base_url

    # ---------- Client 工厂 ----------

    def _create_client(self, cfg: LLMModelConfig) -> BaseLLMClient:
        endpoint = (cfg.endpoint_type or "").lower()
        provider = (cfg.provider or "").lower()

        capabilities = self._capabilities_from_cfg(cfg)
        api_key, base_url = self._resolve_credentials(cfg)

        common_kwargs = dict(
            alias=cfg.alias,
            model=cfg.model_name,
            api_key=api_key,
            base_url=base_url,
            capabilities=capabilities,
            max_input_tokens=cfg.max_input_tokens,
            max_output_tokens=cfg.max_output_tokens,
            embedding_model=None,
        )

        # endpoint_type 决定走哪个 SDK
        if endpoint == "openai":
            # 再根据 provider 区分，便于以后做特化
            if provider == "deepseek":
                return DeepSeekClient(**common_kwargs)
            if provider == "qwen":
                return QwenClient(**common_kwargs)
            return OpenAIClient(**common_kwargs)

        if endpoint == "anthropic":
            return ClaudeClient(**common_kwargs)

        if endpoint == "gemini":
            return GeminiClient(**common_kwargs)

        if endpoint == "ollama":
            return OllamaClient(**common_kwargs)

        # 兜底：走 OpenAI 兼容
        return OpenAIClient(**common_kwargs)

    async def build_all_clients(self) -> Dict[str, BaseLLMClient]:
        """
        初始化所有启用模型的 Client，主要用于测试脚本。
        """
        models = await self.list_enabled_models()
        clients: Dict[str, BaseLLMClient] = {}

        for cfg in models:
            try:
                client = self._create_client(cfg)
            except Exception:
                # 某个模型配置错误不影响其他模型
                continue
            self._client_cache[cfg.alias] = client
            clients[cfg.alias] = client

        return clients

    # ---------- 对外接口 ----------

    async def get_client(self, alias: str) -> BaseLLMClient:
        """
        根据 alias 获取 client。
        - 优先从本地 cache 取
        - 不存在则从 DB 读取配置并创建
        """
        if alias in self._client_cache:
            return self._client_cache[alias]

        async with AsyncSessionFactory() as session:
            stmt = (
                select(LLMModelORM)
                .where(
                    LLMModelORM.alias == alias,
                    LLMModelORM.is_enabled.is_(True),
                )
                .limit(1)
            )
            res = await session.execute(stmt)
            row = res.scalars().first()

        if row is None:
            raise KeyError(f"Unknown or disabled LLM alias: {alias}")

        cfg = self._from_orm(row)
        client = self._create_client(cfg)
        self._client_cache[alias] = client
        return client

    async def get_default_chat_client(self) -> BaseLLMClient:
        """
        获取默认对话模型：
        - 优先 is_default=True 且 support_chat=True
        - 否则选第一个 support_chat=True 的模型
        """
        models = await self.list_enabled_models()
        for cfg in models:
            if cfg.is_default and cfg.support_chat:
                return self._get_or_create_from_cfg(cfg)

        # fallback
        for cfg in models:
            if cfg.support_chat:
                return self._get_or_create_from_cfg(cfg)

        raise RuntimeError("No enabled chat model found")

    async def get_default_embedding_client(self) -> BaseLLMClient:
        """
        获取默认 embedding 模型：
        - 优先 alias 中包含 'embed'/'embedding' 的 support_embeddings=True
        - 否则选第一个 support_embeddings=True 的模型
        """
        models = await self.list_enabled_models()

        candidates = [m for m in models if m.support_embeddings]
        if not candidates:
            raise RuntimeError("No enabled embedding model found")

        # 优先匹配别名包含 'embed'
        for cfg in candidates:
            alias_lower = cfg.alias.lower()
            if "embed" in alias_lower or "embedding" in alias_lower:
                return self._get_or_create_from_cfg(cfg)

        # 否则随便取一个
        return self._get_or_create_from_cfg(candidates[0])

    def _get_or_create_from_cfg(self, cfg: LLMModelConfig) -> BaseLLMClient:
        if cfg.alias in self._client_cache:
            return self._client_cache[cfg.alias]
        client = self._create_client(cfg)
        self._client_cache[cfg.alias] = client
        return client
