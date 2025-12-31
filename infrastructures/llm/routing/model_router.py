# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Model router (configuration-driven). No business logic.

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from domains.llm_model_domain import LlmModelProfile
from infrastructures.llm.config_cache import llm_config_cache
from infrastructures.llm.capability_guard import check_request_capabilities


@dataclass
class RouteResult:
    ok: bool
    profile_id: Optional[str] = None
    reason: Optional[str] = None
    candidates: List[str] = None  # type: ignore[assignment]


class ModelRouter:
    """Select a model profile id based on flow policy and required capabilities."""

    @staticmethod
    async def route(
        db: AsyncSession,
        *,
        flow_code: str,
        need_image: bool = False,
        need_audio: bool = False,
        need_file: bool = False,
        need_stream: bool = False,
        need_json_schema: bool = False,
    ) -> RouteResult:
        snap = await llm_config_cache.ensure_loaded(db)
        flow = snap.flows.get(str(flow_code))
        if flow is None:
            return RouteResult(ok=False, reason="flow_policy_not_found", candidates=[])

        # Candidate order: fallback_chain -> default -> allowed
        ordered: List[str] = []
        for pid in (flow.fallback_chain or []):
            if pid and pid not in ordered:
                ordered.append(pid)
        if flow.default_profile_id and flow.default_profile_id not in ordered:
            ordered.append(flow.default_profile_id)
        for pid in (flow.allowed_profile_ids or []):
            if pid and pid not in ordered:
                ordered.append(pid)

        candidates: List[str] = []
        for pid in ordered:
            prof: Optional[LlmModelProfile] = snap.profiles.get(str(pid))
            if prof is None:
                continue
            if not prof.is_enabled:
                continue

            candidates.append(str(pid))
            chk = check_request_capabilities(
                prof,
                need_image=need_image,
                need_audio=need_audio,
                need_file=need_file,
                need_stream=need_stream,
                need_json_schema=need_json_schema,
            )
            if chk.ok:
                return RouteResult(ok=True, profile_id=str(pid), candidates=candidates)

        return RouteResult(ok=False, reason="no_candidate_satisfies_capability", candidates=candidates)
