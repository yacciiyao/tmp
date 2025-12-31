# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: LLM config read APIs (model profiles & flow policies). Infrastructure-only.

from __future__ import annotations

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_admin
from domains.llm_model_domain import LlmModelProfile, LlmFlowPolicy
from infrastructures.db.orm.orm_deps import get_db
from infrastructures.llm.config_cache import llm_config_cache


router = APIRouter(prefix="/llm", tags=["llm"])


class LlmConfigHealthResp(BaseModel):
    scope: str = "global"
    active_version_id: Optional[int] = None
    loaded_at: int
    profile_count: int
    flow_count: int


class ModelProfilesResp(BaseModel):
    flow_code: Optional[str] = None
    default_profile_id: Optional[str] = None
    models: List[LlmModelProfile] = Field(default_factory=list)


class FlowPoliciesResp(BaseModel):
    flows: List[LlmFlowPolicy] = Field(default_factory=list)


@router.get("/health", response_model=LlmConfigHealthResp)
async def llm_config_health(
    scope: str = Query(default="global", min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
) -> LlmConfigHealthResp:
    """Lightweight health check for LLM config.

    This is NOT a provider health check. It only confirms DB-backed config is readable.
    """

    snap = await llm_config_cache.ensure_loaded(db, scope=str(scope))
    return LlmConfigHealthResp(
        scope=str(scope),
        active_version_id=snap.version_id,
        loaded_at=int(snap.loaded_at),
        profile_count=len(snap.profiles),
        flow_count=len(snap.flows),
    )


@router.post("/admin/reload")
async def reload_llm_config(
    scope: str = Query(default="global", min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> Dict[str, Any]:
    """Force reload LLM config cache.

    Requires admin.
    """

    llm_config_cache.invalidate()
    snap = await llm_config_cache.ensure_loaded(db, scope=str(scope))
    return {
        "status": "ok",
        "scope": str(scope),
        "active_version_id": snap.version_id,
        "profile_count": len(snap.profiles),
        "flow_count": len(snap.flows),
        "loaded_at": int(snap.loaded_at),
    }


@router.get("/model-profiles", response_model=ModelProfilesResp)
async def list_model_profiles(
    flow_code: Optional[str] = Query(default=None, min_length=3, max_length=64),
    db: AsyncSession = Depends(get_db),
) -> ModelProfilesResp:
    """List available model profiles.

    - If flow_code is provided: returns only the profiles allowed by the flow policy (enabled ones).
    - Otherwise: returns all profiles (including disabled ones), for admin/debug purposes.
    """

    snap = await llm_config_cache.ensure_loaded(db)

    if flow_code:
        flow = snap.flows.get(str(flow_code))
        models = await llm_config_cache.list_allowed_profiles(db, str(flow_code))
        return ModelProfilesResp(
            flow_code=str(flow_code),
            default_profile_id=flow.default_profile_id if flow else None,
            models=models,
        )

    # list all (including disabled)
    models_all = sorted(snap.profiles.values(), key=lambda x: x.profile_id)
    return ModelProfilesResp(flow_code=None, default_profile_id=None, models=models_all)


@router.get("/flow-policies", response_model=FlowPoliciesResp)
async def list_flow_policies(
    flow_code: Optional[str] = Query(default=None, min_length=3, max_length=64),
    db: AsyncSession = Depends(get_db),
) -> FlowPoliciesResp:
    """List LLM flow policies."""

    snap = await llm_config_cache.ensure_loaded(db)
    if flow_code:
        flow = snap.flows.get(str(flow_code))
        return FlowPoliciesResp(flows=[flow] if flow else [])

    flows_all = sorted(snap.flows.values(), key=lambda x: x.flow_code)
    return FlowPoliciesResp(flows=flows_all)
