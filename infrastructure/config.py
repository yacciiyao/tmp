# -*- coding: utf-8 -*-
# @File: config.py
# @Author: yaccii
# @Description:
from __future__ import annotations

import os
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


class Settings(BaseModel):
    # 应用
    app_env: str = Field(default="dev")  # dev / prod / test
    debug: bool = Field(default=True)

    # 日志
    log_level: str = Field(default="INFO")  # DEBUG / INFO / WARNING / ERROR

    db_url: str  # mysql+aiomysql://user:pwd@host:3306/dbname

    # SQLAlchemy 日志
    sql_echo: bool = Field(default=False)

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=1440)

    # 默认 LLM 标识
    default_llm: str = Field(default="openai:gpt-4o-mini")

    # LLM / Embedding key
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None

    deepseek_api_key: Optional[str] = None
    deepseek_base_url: Optional[str] = None

    qwen_api_key: Optional[str] = None
    qwen_base_url: Optional[str] = None

    claude_api_key: Optional[str] = None
    claude_base_url: Optional[str] = None

    gemini_api_key: Optional[str] = None
    gemini_base_url: Optional[str] = None

    # 本地模型（如 Ollama / 内网推理服务）
    local_llm_endpoint: Optional[str] = None

    # CORS
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])

    # Elasticsearch（混合检索用，先预留）
    es_host: str = Field(default="127.0.0.1")
    es_port: int = Field(default=9200)
    es_scheme: str = Field(default="http")
    es_username: Optional[str] = None
    es_password: Optional[str] = None
    es_index_prefix: str = Field(default="mah_")

    # 向量库
    vector_store_type: str = Field(default="faiss")  # faiss / milvus
    faiss_dir: str = Field(default="./data/faiss")
    milvus_uri: Optional[str] = None
    milvus_username: Optional[str] = None
    milvus_password: Optional[str] = None

    # 文件存储
    file_storage_root: str = Field(default="./data/files")
    file_base_url: Optional[str] = None

    # OCR / 多模态
    ocr_provider: str = Field(default="none")  # none / openai / gemini / custom
    ocr_endpoint: Optional[str] = None
    ocr_api_key: Optional[str] = None


def _str_to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


def _load_settings() -> Settings:
    load_dotenv()

    db_url = os.getenv("DB_URL")
    jwt_secret_key = os.getenv("JWT_SECRET_KEY")

    if not db_url:
        raise RuntimeError("Missing DB_URL in environment/.env")
    if not jwt_secret_key:
        raise RuntimeError("Missing JWT_SECRET_KEY in environment/.env")

    app_env = os.getenv("APP_ENV", "dev")
    debug = _str_to_bool(os.getenv("APP_DEBUG"), True)

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    sql_echo = _str_to_bool(os.getenv("SQL_ECHO"), debug)

    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    try:
        jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
    except ValueError:
        jwt_expire_minutes = 1440

    default_llm = os.getenv("DEFAULT_LLM", "openai:gpt-4o-mini")

    cors_raw = os.getenv("CORS_ORIGINS", "*")
    if cors_raw.strip() == "*":
        cors_origins = ["*"]
    else:
        cors_origins = [x.strip() for x in cors_raw.split(",") if x.strip()]

    es_host = os.getenv("ES_HOST", "127.0.0.1")
    try:
        es_port = int(os.getenv("ES_PORT", "9200"))
    except ValueError:
        es_port = 9200
    es_scheme = os.getenv("ES_SCHEME", "http")
    es_username = os.getenv("ES_USERNAME")
    es_password = os.getenv("ES_PASSWORD")
    es_index_prefix = os.getenv("ES_INDEX_PREFIX", "mah_")

    vector_store_type = os.getenv("VECTOR_STORE_TYPE", "faiss")
    faiss_dir = os.getenv("FAISS_DIR", "./data/faiss")
    milvus_uri = os.getenv("MILVUS_URI")
    milvus_username = os.getenv("MILVUS_USERNAME")
    milvus_password = os.getenv("MILVUS_PASSWORD")

    file_storage_root = os.getenv("FILE_STORAGE_ROOT", "./data/files")
    file_base_url = os.getenv("FILE_BASE_URL")

    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL")

    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL")

    qwen_api_key = os.getenv("QWEN_API_KEY")
    qwen_base_url = os.getenv("QWEN_BASE_URL")

    claude_api_key = os.getenv("CLAUDE_API_KEY")
    claude_base_url = os.getenv("CLAUDE_BASE_URL")

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    gemini_base_url = os.getenv("GEMINI_BASE_URL")

    local_llm_endpoint = os.getenv("LOCAL_LLM_ENDPOINT")

    ocr_provider = os.getenv("OCR_PROVIDER", "none")
    ocr_endpoint = os.getenv("OCR_ENDPOINT")
    ocr_api_key = os.getenv("OCR_API_KEY")

    data = {
        "app_env": app_env,
        "debug": debug,
        "log_level": log_level,
        "db_url": db_url,
        "sql_echo": sql_echo,
        "jwt_secret_key": jwt_secret_key,
        "jwt_algorithm": jwt_algorithm,
        "jwt_expire_minutes": jwt_expire_minutes,
        "default_llm": default_llm,
        "openai_api_key": openai_api_key,
        "openai_base_url": openai_base_url,
        "deepseek_api_key": deepseek_api_key,
        "deepseek_base_url": deepseek_base_url,
        "qwen_api_key": qwen_api_key,
        "qwen_base_url": qwen_base_url,
        "claude_api_key": claude_api_key,
        "claude_base_url": claude_base_url,
        "gemini_api_key": gemini_api_key,
        "gemini_base_url": gemini_base_url,
        "local_llm_endpoint": local_llm_endpoint,
        "cors_origins": cors_origins,
        "es_host": es_host,
        "es_port": es_port,
        "es_scheme": es_scheme,
        "es_username": es_username,
        "es_password": es_password,
        "es_index_prefix": es_index_prefix,
        "vector_store_type": vector_store_type,
        "faiss_dir": faiss_dir,
        "milvus_uri": milvus_uri,
        "milvus_username": milvus_username,
        "milvus_password": milvus_password,
        "file_storage_root": file_storage_root,
        "file_base_url": file_base_url,
        "ocr_provider": ocr_provider,
        "ocr_endpoint": ocr_endpoint,
        "ocr_api_key": ocr_api_key,
    }

    try:
        return Settings(**data)
    except ValidationError as e:
        raise RuntimeError(f"Invalid settings: {e}") from e


settings = _load_settings()
