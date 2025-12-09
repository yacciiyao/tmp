# -*- coding: utf-8 -*-
# @File: model.py
# @Author: yaccii
# @Description:
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMModelCapabilities:
    chat: bool = True
    stream: bool = True
    embeddings: bool = False
    rerank: bool = False
    vision: bool = False
    image: bool = False
    audio_stt: bool = False
    audio_tts: bool = False


@dataclass
class LLMModel:

    id: int
    alias: str                 # 前端 / 后端统一使用的模型 ID
    name: str                  # 展示名称

    provider: str              # openai / anthropic / google / deepseek / qwen / ollama / ...
    endpoint_type: str         # openai-native / openai-compatible / anthropic / gemini / ollama-native / ...
    model_name: str            # 真实模型名，例如 gpt-4o-mini / llama3:8b / qwen2:7b

    source: str                # cloud / local / proxy
    family: Optional[str]      # gpt-4o / llama3 / qwen2 / ...

    # 从哪个环境变量里取 base_url / api_key（支持走代理，不在代码里写任何 CLOSEAI_xxx）
    base_url_env: Optional[str]
    api_key_env: Optional[str]

    capabilities: LLMModelCapabilities

    max_input_tokens: Optional[int]
    max_output_tokens: Optional[int]

    is_default: bool
    is_enabled: bool

    remark: Optional[str] = None

