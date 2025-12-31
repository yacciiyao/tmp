# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: LLM module ORM (service DB).

from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String, Text, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from infrastructures.db.orm.orm_base import Base, TimestampMixin


class LlmModelProfilesORM(Base, TimestampMixin):
    """Model profiles registry (DB-backed).

    Stores capability map used by the UI (button gating) and backend guards.
    """

    __tablename__ = "llm_model_profiles"

    profile_id: Mapped[str] = mapped_column(String(128), primary_key=True)

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)

    is_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="1=enabled,0=disabled")

    capabilities_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    limits_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("idx_llm_profile_provider", "provider"),
        Index("idx_llm_profile_enabled", "is_enabled"),
    )


class LlmFlowPoliciesORM(Base, TimestampMixin):
    """Default model selection & constraints per business flow."""

    __tablename__ = "llm_flow_policies"

    flow_code: Mapped[str] = mapped_column(String(64), primary_key=True)

    default_profile_id: Mapped[str] = mapped_column(String(128), nullable=False)
    allowed_profile_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    fallback_chain_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    default_rag_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    default_stream_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    multimodal_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="BLOCK")

    params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("idx_llm_flow_default", "default_profile_id"),
    )


class LlmConfigVersionsORM(Base, TimestampMixin):
    """Optional versioning for bulk config publish & rollback."""

    __tablename__ = "llm_config_versions"

    version_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="global")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="1=ACTIVE,0=INACTIVE")
    published_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("idx_llm_cfg_scope_status", "scope", "status"),
    )
