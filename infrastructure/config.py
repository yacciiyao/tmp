# -*- coding: utf-8 -*-
# @File: config.py

from __future__ import annotations

import os
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


def _str_to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _parse_csv(value: str | None) -> List[str]:
    if not value:
        return []
    raw = value.strip()
    if raw == "*":
        return ["*"]
    parts = [x.strip() for x in raw.split(",")]
    return [x for x in parts if x]


class Settings(BaseModel):
    # ---------- app ----------
    app_env: str = Field(default="dev")  # dev / prod / test
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    sql_echo: bool = Field(default=False)

    # ---------- db ----------
    db_url: str

    # ---------- jwt ----------
    jwt_secret_key: str
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=1440)

    # ---------- admin bootstrap ----------
    default_admin_username: str = Field(default="admin")
    default_admin_password: str = Field(default="admin123")

    # ---------- CORS ----------
    cors_origins: List[str] = Field(default_factory=list)

    @property
    def cors_allow_credentials(self) -> bool:
        # 允许 "*" 时必须禁止 credentials
        return self.cors_origins != ["*"]

    # ---------- LLM routing hints (optional) ----------
    # 注意：真正可用模型来自 llm_model 表；这里是“默认偏好/前端默认值”的提示位
    default_llm_alias: Optional[str] = None
    embedding_llm_alias: Optional[str] = None

    # ---------- provider keys (optional; many are actually read by LLMRegistry via env names in DB) ----------
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
    local_llm_endpoint: Optional[str] = None

    # ---------- RAG / storage ----------
    es_host: str = Field(default="127.0.0.1")
    es_port: int = Field(default=9200)
    es_scheme: str = Field(default="http")
    es_username: Optional[str] = None
    es_password: Optional[str] = None
    es_index_prefix: str = Field(default="mah_")

    vector_store_type: str = Field(default="faiss")
    faiss_dir: str = Field(default="./data/faiss")
    milvus_uri: Optional[str] = None
    milvus_username: Optional[str] = None
    milvus_password: Optional[str] = None

    file_storage_root: str = Field(default="./data/files")
    file_base_url: Optional[str] = None

    # ---------- OCR / multimodal ----------
    ocr_provider: str = Field(default="none")
    ocr_endpoint: Optional[str] = None
    ocr_api_key: Optional[str] = None


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

    cors_origins = _parse_csv(os.getenv("CORS_ORIGINS", ""))

    default_admin_username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    default_admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

    default_llm_alias = os.getenv("DEFAULT_LLM_ALIAS")
    embedding_llm_alias = os.getenv("EMBEDDING_LLM_ALIAS")

    # RAG / storage / providers
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
    claude_api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    claude_base_url = os.getenv("CLAUDE_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL")
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
        "sql_echo": sql_echo,
        "db_url": db_url,
        "jwt_secret_key": jwt_secret_key,
        "jwt_algorithm": jwt_algorithm,
        "jwt_expire_minutes": jwt_expire_minutes,
        "default_admin_username": default_admin_username,
        "default_admin_password": default_admin_password,
        "cors_origins": cors_origins,
        "default_llm_alias": default_llm_alias,
        "embedding_llm_alias": embedding_llm_alias,
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
        "ocr_provider": ocr_provider,
        "ocr_endpoint": ocr_endpoint,
        "ocr_api_key": ocr_api_key,
    }

    try:
        return Settings(**data)
    except ValidationError as e:
        raise RuntimeError(f"Invalid settings: {e}") from e


settings = _load_settings()
