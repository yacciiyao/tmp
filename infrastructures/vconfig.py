# -*- coding: utf-8 -*-
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


class VConfig(BaseSettings):
    """Project configuration loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=str(_project_root() / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- App & Logging ----------
    app_env: str = Field(..., validation_alias="APP_ENV")
    log_level: str = Field(..., validation_alias="LOG_LEVEL")
    log_requests: bool = Field(..., validation_alias="LOG_REQUESTS")
    request_id_header: str = Field(..., validation_alias="REQUEST_ID_HEADER")
    generate_request_id: bool = Field(..., validation_alias="GENERATE_REQUEST_ID")

    cors_origins: str = Field(..., validation_alias="CORS_ORIGINS")

    # ---------- Upload ----------
    max_upload_mb: int = Field(..., validation_alias="MAX_UPLOAD_MB", ge=1)

    # ---------- Database ----------
    db_url: str = Field(..., validation_alias="DB_URL")
    sql_echo: bool = Field(False, validation_alias="SQL_ECHO")

    # ---------- Auth/JWT ----------
    jwt_secret_key: str = Field(..., validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(..., validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(..., validation_alias="JWT_EXPIRE_MINUTES", ge=1)

    default_admin_username: str = Field(..., validation_alias="DEFAULT_ADMIN_USERNAME")
    default_admin_password: str = Field(..., validation_alias="DEFAULT_ADMIN_PASSWORD")

    # ---------- Storage ----------
    storage_dir: str = Field(..., validation_alias="STORAGE_DIR")

    # ---------- Worker ----------
    worker_poll_interval: float = Field(..., validation_alias="WORKER_POLL_INTERVAL", gt=0)

    # ---------- Search ----------
    index_backend: str = Field(..., validation_alias="INDEX_BACKEND")
    search_max_per_doc: int = Field(..., validation_alias="SEARCH_MAX_PER_DOC", ge=1)

    # ---------- Embedding ----------
    embedding_backend: str = Field(..., validation_alias="EMBEDDING_BACKEND")
    embedding_model_name: str = Field(..., validation_alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(..., validation_alias="EMBEDDING_DIM", ge=1)

    # ---------- Elasticsearch (optional) ----------
    es_enabled: bool = Field(False, validation_alias="ES_ENABLED")
    es_url: str = Field("", validation_alias="ES_URL")
    es_username: str = Field("", validation_alias="ES_USERNAME")
    es_password: str = Field("", validation_alias="ES_PASSWORD")
    es_api_key: str = Field("", validation_alias="ES_API_KEY")
    es_index_prefix: str = Field("veesees_chunks_", validation_alias="ES_INDEX_PREFIX")
    es_timeout_seconds: int = Field(10, validation_alias="ES_TIMEOUT_SECONDS", ge=1)
    es_number_of_shards: int = Field(1, validation_alias="ES_NUMBER_OF_SHARDS", ge=1)
    es_number_of_replicas: int = Field(0, validation_alias="ES_NUMBER_OF_REPLICAS", ge=0)

    # ---------- Milvus (optional) ----------
    milvus_enabled: bool = Field(False, validation_alias="MILVUS_ENABLED")
    milvus_uri: str = Field("", validation_alias="MILVUS_URI")
    milvus_token: str = Field("", validation_alias="MILVUS_TOKEN")
    milvus_username: str = Field("", validation_alias="MILVUS_USERNAME")
    milvus_password: str = Field("", validation_alias="MILVUS_PASSWORD")
    milvus_database: str = Field("default", validation_alias="MILVUS_DATABASE")
    milvus_secure: bool = Field(False, validation_alias="MILVUS_SECURE")
    milvus_collection_prefix: str = Field("rag", validation_alias="MILVUS_COLLECTION_PREFIX")

    milvus_metric_type: str = Field("COSINE", validation_alias="MILVUS_METRIC_TYPE")
    milvus_index_type: str = Field("HNSW", validation_alias="MILVUS_INDEX_TYPE")
    milvus_hnsw_m: int = Field(16, validation_alias="MILVUS_HNSW_M", ge=1)
    milvus_hnsw_ef_construction: int = Field(200, validation_alias="MILVUS_HNSW_EF_CONSTRUCTION", ge=1)
    milvus_search_nprobe: int = Field(16, validation_alias="MILVUS_SEARCH_NPROBE", ge=1)
    milvus_search_ef: int = Field(64, validation_alias="MILVUS_SEARCH_EF", ge=1)
    milvus_index_params: str = Field("", validation_alias="MILVUS_INDEX_PARAMS")

    # ---------- Parsing extras (optional) ----------
    enable_image_ocr: bool = Field(False, validation_alias="ENABLE_IMAGE_OCR")
    ocr_lang: str = Field("ch", validation_alias="OCR_LANG")

    enable_audio_asr: bool = Field(False, validation_alias="ENABLE_AUDIO_ASR")
    whisper_model_size: str = Field("base", validation_alias="WHISPER_MODEL_SIZE")
    whisper_device: str = Field("cpu", validation_alias="WHISPER_DEVICE")
    whisper_compute_type: str = Field("int8", validation_alias="WHISPER_COMPUTE_TYPE")
    whisper_language: Optional[str] = Field(None, validation_alias="WHISPER_LANGUAGE")

    @field_validator("whisper_language", mode="before")
    @classmethod
    def _normalize_whisper_language(cls, v):
        # "" -> None, avoid faster-whisper language validation error
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("ocr_lang", mode="before")
    @classmethod
    def _normalize_ocr_lang(cls, v):
        # "" -> "ch"
        if v is None:
            return "ch"
        if isinstance(v, str) and not v.strip():
            return "ch"
        return v


@lru_cache(maxsize=1)
def get_config() -> VConfig:
    return VConfig()


config = get_config()
