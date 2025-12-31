# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: LLM executor (routing + preprocess + provider call). Infrastructure-only.

from __future__ import annotations

from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from domains.llm_model_domain import LlmModelProfile
from domains.llm_request_domain import LlmRequest, LlmResponse, StreamEvent
from infrastructures.llm.config_cache import llm_config_cache
from infrastructures.llm.errors import LlmConfigError
from infrastructures.llm.preprocess.multimodal_assist import MultimodalAssistPreprocessor
from infrastructures.llm.provider_registry import get_provider
from infrastructures.parsing.local_parser import LocalParser


class LlmExecutor:
    """Infrastructure executor.

    Responsibilities:
      1) resolve model profile from DB-backed cache (by req.model_profile_id)
      2) apply deterministic ASSIST preprocessing if model requires it
      3) call provider adapter generate/stream

    It does NOT implement business flow (sessions, RAG prompting, VOC logic, etc.).
    """

    def __init__(self) -> None:
        self._parser = LocalParser()
        self._pre = MultimodalAssistPreprocessor(parser=self._parser)

    async def _resolve_profile(self, db: AsyncSession, model_profile_id: str) -> LlmModelProfile:
        prof = await llm_config_cache.get_profile(db, str(model_profile_id))
        if prof is None:
            raise LlmConfigError("model profile not found", details={"profile_id": str(model_profile_id)})
        return prof

    async def generate(self, *, db: AsyncSession, req: LlmRequest, profile: Optional[LlmModelProfile] = None) -> LlmResponse:
        prof = profile or await self._resolve_profile(db, req.model_profile_id)
        req2 = await self._pre.preprocess(req=req, profile=prof)

        provider = get_provider(prof.provider.value)
        if provider is None:
            raise LlmConfigError("provider not registered", details={"provider": prof.provider.value})
        return await provider.generate(req2)

    async def stream(self, *, db: AsyncSession, req: LlmRequest, profile: Optional[LlmModelProfile] = None) -> AsyncIterator[StreamEvent]:
        prof = profile or await self._resolve_profile(db, req.model_profile_id)
        req2 = await self._pre.preprocess(req=req, profile=prof)

        provider = get_provider(prof.provider.value)
        if provider is None:
            raise LlmConfigError("provider not registered", details={"provider": prof.provider.value})

        async for ev in provider.stream(req2):
            yield ev


llm_executor = LlmExecutor()
