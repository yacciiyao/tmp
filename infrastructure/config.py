# -*- coding: utf-8 -*-
# @File: infrastructure/config.py
# @Author: yaccii
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

    # 数据库
    db_url: str  # mysql+aiomysql://user:pwd@host:3306/dbname
    sql_echo: bool = Field(default=False)

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=1440)

    # 默认 LLM 标识
    default_llm: str = Field(default="openai:gpt-4o-mini")

    # LLM / Embedding keys & endpoints
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

    # Elasticsearch
    es_enabled: bool = Field(default=False)  # 关键新增：控制 ESClient NO-OP
    es_host: str = Field(default="127.0.0.1")
    es_port: int = Field(default=9200)
    es_scheme: str = Field(default="http")
    es_username: Optional[str] = None
    es_password: Optional[str] = None
    es_index_prefix: str = Field(default="mah")  # 与 .env 中 ES_INDEX_PREFIX 对齐
    es_number_of_shards: int = Field(default=1)
    es_number_of_replicas: int = Field(default=0)

    # 向量库
    vector_store_type: str = Field(default="faiss")  # faiss / milvus
    faiss_dir: str = Field(default="./data/faiss")
    milvus_uri: Optional[str] = None
    milvus_username: Optional[str] = None
    milvus_password: Optional[str] = None
    milvus_database: str = Field(default="default")             # 关键新增：manager.py 里用到
    milvus_collection_prefix: str = Field(default="rag")        # 关键新增：manager.py 里用到

    # 文件存储
    file_storage_backend: str = Field(default="local")          # local | s3
    file_storage_root: str = Field(default="./data/files")      # local 用
    file_base_url: Optional[str] = None                         # 公网访问前缀（可空）

    # S3 配置（当 backend=s3 时使用）
    s3_endpoint_url: Optional[str] = None
    s3_region: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_access_key_id: Optional[str] = None
    s3_secret_access_key: Optional[str] = None
    s3_force_path_style: bool = Field(default=False)
    s3_base_url: Optional[str] = None  # 可选的直链前缀（CDN/反代）

    # OCR / 多模态
    ocr_provider: str = Field(default="none")  # none / openai / gemini / custom
    ocr_endpoint: Optional[str] = None
    ocr_api_key: Optional[str] = None

    # 默认管理员初始化
    default_admin_username: str = Field(default="admin")
    default_admin_password: str = Field(default="admin123")


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

    # 同时兼容 DEBUG 与 APP_DEBUG（以 DEBUG 为主）
    debug = _str_to_bool(os.getenv("DEBUG") or os.getenv("APP_DEBUG"), True)

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

    # ES
    es_enabled = _str_to_bool(os.getenv("ES_ENABLED"), False)
    es_host = os.getenv("ES_HOST", "127.0.0.1")
    try:
        es_port = int(os.getenv("ES_PORT", "9200"))
    except ValueError:
        es_port = 9200
    es_scheme = os.getenv("ES_SCHEME", "http")
    es_username = os.getenv("ES_USERNAME")
    es_password = os.getenv("ES_PASSWORD")
    es_index_prefix = os.getenv("ES_INDEX_PREFIX", "mah")
    es_number_of_shards = int(os.getenv("ES_NUMBER_OF_SHARDS", "1"))
    es_number_of_replicas = int(os.getenv("ES_NUMBER_OF_REPLICAS", "0"))

    # Vector store
    vector_store_type = os.getenv("VECTOR_STORE_TYPE", "faiss")
    faiss_dir = os.getenv("FAISS_DIR", "./data/faiss")
    milvus_uri = os.getenv("MILVUS_URI")
    milvus_username = os.getenv("MILVUS_USERNAME")
    milvus_password = os.getenv("MILVUS_PASSWORD")
    milvus_database = os.getenv("MILVUS_DATABASE", "default")
    milvus_collection_prefix = os.getenv("MILVUS_COLLECTION_PREFIX", "rag")

    # File storage
    file_storage_backend = os.getenv("FILE_STORAGE_BACKEND", "local")
    file_storage_root = os.getenv("FILE_STORAGE_ROOT", "./data/files")
    file_base_url = os.getenv("FILE_BASE_URL")

    # S3
    s3_endpoint_url = os.getenv("S3_ENDPOINT_URL")
    s3_region = os.getenv("S3_REGION")
    s3_bucket = os.getenv("S3_BUCKET")
    s3_access_key_id = os.getenv("S3_ACCESS_KEY_ID")
    s3_secret_access_key = os.getenv("S3_SECRET_ACCESS_KEY")
    s3_force_path_style = _str_to_bool(os.getenv("S3_FORCE_PATH_STYLE"), False)
    s3_base_url = os.getenv("S3_BASE_URL")

    # LLM keys
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

    # OCR
    ocr_provider = os.getenv("OCR_PROVIDER", "none")
    ocr_endpoint = os.getenv("OCR_ENDPOINT")
    ocr_api_key = os.getenv("OCR_API_KEY")

    # 默认管理员
    default_admin_username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    default_admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

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
        "es_enabled": es_enabled,
        "es_host": es_host,
        "es_port": es_port,
        "es_scheme": es_scheme,
        "es_username": es_username,
        "es_password": es_password,
        "es_index_prefix": es_index_prefix,
        "es_number_of_shards": es_number_of_shards,
        "es_number_of_replicas": es_number_of_replicas,
        "vector_store_type": vector_store_type,
        "faiss_dir": faiss_dir,
        "milvus_uri": milvus_uri,
        "milvus_username": milvus_username,
        "milvus_password": milvus_password,
        "milvus_database": milvus_database,
        "milvus_collection_prefix": milvus_collection_prefix,
        "file_storage_backend": file_storage_backend,
        "file_storage_root": file_storage_root,
        "file_base_url": file_base_url,
        "s3_endpoint_url": s3_endpoint_url,
        "s3_region": s3_region,
        "s3_bucket": s3_bucket,
        "s3_access_key_id": s3_access_key_id,
        "s3_secret_access_key": s3_secret_access_key,
        "s3_force_path_style": s3_force_path_style,
        "s3_base_url": s3_base_url,
        "ocr_provider": ocr_provider,
        "ocr_endpoint": ocr_endpoint,
        "ocr_api_key": ocr_api_key,
        "default_admin_username": default_admin_username,
        "default_admin_password": default_admin_password,
    }

    try:
        return Settings(**data)
    except ValidationError as e:
        raise RuntimeError(f"Invalid settings: {e}") from e


settings = _load_settings()
