# -*- coding: utf-8 -*-
# @File: model_orm.py
# @Author: yaccii
# @Description:

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base, TimestampMixin


class LLMModelORM(TimestampMixin, Base):
    """
    大模型配置表：
    - 有哪些可用模型（alias）
    - 模型的基础信息: provider / model_name / base_url_env / api_key_env
    - 模型的能力矩阵（是否支持多模态等）
    """
    __tablename__ = "llm_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 别名：前端/会话/日志用这个字段（如 gpt-4o-mini / deepseek-chat / gemini-flash / ollama-llama3）
    alias: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # 人类可读名称
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # 提供方：openai / deepseek / gemini / qwen / claude / ollama / ...
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # 接入协议：openai / anthropic / gemini / ollama / ...
    endpoint_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # 真实模型名：发给 SDK/HTTP 的 model 参数
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # 来源：cloud / local / proxy 等，主要用于运维和展示
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="cloud")
    # 模型家族：gpt-4 / llama3 / qwen2 / deepseek-chat ...
    family: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # 各自从 .env 获取 base_url / api_key 的环境变量名（可为空）
    base_url_env: Mapped[str | None] = mapped_column(String(64), nullable=True)
    api_key_env: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ---- 能力矩阵 ----
    support_chat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    support_stream: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    support_embeddings: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    support_rerank: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    support_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)        # 图文理解
    support_image: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)         # 文生图
    support_audio_stt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)     # 语音转文本
    support_audio_tts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)     # 文本转语音

    max_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 是否默认对话模型
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 是否启用
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 备注说明
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
