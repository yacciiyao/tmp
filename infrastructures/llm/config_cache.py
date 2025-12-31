# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: DB-backed LLM config cache (model profiles & flow policies).

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from domains.llm_model_domain import LlmModelProfile, LlmFlowPolicy
from infrastructures.db.repository.llm_config_repository import LlmConfigRepository


def _now() -> int:
    return int(time.time())


@dataclass
class LlmConfigSnapshot:
    loaded_at: int
    profiles: Dict[str, LlmModelProfile]
    flows: Dict[str, LlmFlowPolicy]
    version_id: Optional[int] = None


class LlmConfigCache:
    """In-memory cache for LLM config.

    - The *source of truth* is service DB tables: llm_model_profiles, llm_flow_policies.
    - The cache is intentionally simple: TTL-based refresh with optional version check.

    This module is infrastructure-only: callers should provide a db session.
    """

    def __init__(self, *, ttl_seconds: int = 60):
        self._ttl = max(5, int(ttl_seconds))
        self._snapshot: Optional[LlmConfigSnapshot] = None
        self._lock = asyncio.Lock()

    def invalidate(self) -> None:
        """Invalidate local cache.

        Useful for admin/config update flows.
        """

        self._snapshot = None

    @property
    def snapshot(self) -> Optional[LlmConfigSnapshot]:
        return self._snapshot

    def _is_fresh(self) -> bool:
        if self._snapshot is None:
            return False
        return (_now() - int(self._snapshot.loaded_at)) < self._ttl

    async def ensure_loaded(self, db: AsyncSession, *, scope: str = "global") -> LlmConfigSnapshot:
        """Load config if cache is empty or stale.

        If config_versions table is used, this method also checks active version id.
        """

        if self._is_fresh():
            return self._snapshot  # type: ignore[return-value]

        # Prevent thundering herd under concurrency: only one coroutine refreshes.
        async with self._lock:
            if self._is_fresh():
                return self._snapshot  # type: ignore[return-value]

            active_ver = await LlmConfigRepository.get_active_version(db, scope=str(scope))
            version_id = int(active_ver.version_id) if active_ver is not None else None

            # If we had a snapshot and version didn't change, treat as fresh (even if TTL passed).
            if self._snapshot is not None and version_id is not None and self._snapshot.version_id == version_id:
                self._snapshot.loaded_at = _now()
                return self._snapshot

            profiles_orm = await LlmConfigRepository.list_model_profiles(db, enabled_only=False, limit=2000)
            flows_orm = await LlmConfigRepository.list_flow_policies(db, limit=2000)

            profiles: Dict[str, LlmModelProfile] = {}
            for row in profiles_orm:
                cap = dict(row.capabilities_json or {})
                # Backward/forward compatibility: allow limits_json to override/merge.
                if row.limits_json:
                    if isinstance(cap.get("limits"), dict):
                        merged = dict(cap["limits"])  # type: ignore[index]
                        merged.update(dict(row.limits_json or {}))
                        cap["limits"] = merged
                    elif "limits" not in cap:
                        cap["limits"] = dict(row.limits_json or {})

                profiles[str(row.profile_id)] = LlmModelProfile(
                    profile_id=str(row.profile_id),
                    provider=str(row.provider),  # enum will validate
                    model_name=str(row.model_name),
                    display_name=str(row.display_name),
                    is_enabled=bool(int(row.is_enabled or 0) == 1),
                    capabilities=cap,
                    meta=(row.meta_json or {}),
                )

            flows: Dict[str, LlmFlowPolicy] = {}
            for row in flows_orm:
                flows[str(row.flow_code)] = LlmFlowPolicy(
                    flow_code=str(row.flow_code),
                    default_profile_id=str(row.default_profile_id),
                    allowed_profile_ids=list(row.allowed_profile_ids_json or []),
                    fallback_chain=list(row.fallback_chain_json or []),
                    default_rag_enabled=bool(int(row.default_rag_enabled or 0) == 1),
                    default_stream_enabled=bool(int(row.default_stream_enabled or 0) == 1),
                    multimodal_policy=str(row.multimodal_policy or "BLOCK"),
                    params=(row.params_json or {}),
                )

            self._snapshot = LlmConfigSnapshot(loaded_at=_now(), profiles=profiles, flows=flows, version_id=version_id)
            return self._snapshot

    async def get_profile(self, db: AsyncSession, profile_id: str) -> Optional[LlmModelProfile]:
        snap = await self.ensure_loaded(db)
        return snap.profiles.get(str(profile_id))

    async def get_flow(self, db: AsyncSession, flow_code: str) -> Optional[LlmFlowPolicy]:
        snap = await self.ensure_loaded(db)
        return snap.flows.get(str(flow_code))

    async def list_allowed_profiles(self, db: AsyncSession, flow_code: str) -> List[LlmModelProfile]:
        snap = await self.ensure_loaded(db)
        flow = snap.flows.get(str(flow_code))
        if flow is None:
            return []

        allowed_ids = flow.allowed_profile_ids or [flow.default_profile_id]
        out: List[LlmModelProfile] = []
        for pid in allowed_ids:
            p = snap.profiles.get(str(pid))
            if p is None:
                continue
            if not p.is_enabled:
                continue
            out.append(p)
        return out


# A process-local singleton is typically fine; refresh controlled by TTL/version.
llm_config_cache = LlmConfigCache(ttl_seconds=60)
