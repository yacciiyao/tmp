# -*- coding: utf-8 -*-
# @File: application/model/dto.py
# @Author: yaccii
# @Description: LLM 模型管理 DTO

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class LLMModelBase(BaseModel):
    name: str
    provider: str
    endpoint_type: str
    model_name: str

    source: str = "cloud"          # cloud / local
    family: Optional[str] = None   # gpt-4o / llama3 / qwen2 ...

    base_url_env: Optional[str] = None
    api_key_env: Optional[str] = None

    support_chat: bool = True
    support_stream: bool = True
    support_embeddings: bool = False
    support_rerank: bool = False
    support_vision: bool = False
    support_image: bool = False
    support_audio_stt: bool = False
    support_audio_tts: bool = False

    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None

    is_default: bool = False
    is_enabled: bool = True

    remark: Optional[str] = None


class LLMModelCreate(LLMModelBase):
    alias: str


class LLMModelUpdate(BaseModel):
    # 全部可选，PATCH 语义
    name: Optional[str] = None
    provider: Optional[str] = None
    endpoint_type: Optional[str] = None
    model_name: Optional[str] = None

    source: Optional[str] = None
    family: Optional[str] = None

    base_url_env: Optional[str] = None
    api_key_env: Optional[str] = None

    support_chat: Optional[bool] = None
    support_stream: Optional[bool] = None
    support_embeddings: Optional[bool] = None
    support_rerank: Optional[bool] = None
    support_vision: Optional[bool] = None
    support_image: Optional[bool] = None
    support_audio_stt: Optional[bool] = None
    support_audio_tts: Optional[bool] = None

    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None

    is_default: Optional[bool] = None
    is_enabled: Optional[bool] = None

    remark: Optional[str] = None


class LLMModelOut(LLMModelBase):
    id: int
    alias: str
    created_at: int
    updated_at: int

    class Config:
        from_attributes = True  # pydantic v2: 支持 ORM 对象
