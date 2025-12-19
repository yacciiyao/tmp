# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: space -> document -> chunk, jobs
from __future__ import annotations

from enum import Enum, IntEnum
from typing import Any, Dict, Optional, List

from pydantic import Field

from domains.domain_base import DomainModel, now_ts


class SpaceStatus(IntEnum):
    DISABLED = 0  # 停用（不可用）
    ENABLED = 1  # 启用（可用）


class DocumentStatus(IntEnum):
    UPLOADED = 10  # 已上传（文件已落盘/对象存储，但尚未入库）
    PROCESSING = 20  # 入库中（解析、切分、向量化、写索引）
    INDEXED = 30  # 已入库（可检索）
    FAILED = 40  # 入库失败（达到最大重试/不可重试）
    DELETED = 90  # 已删除（软删）


class JobStatus(IntEnum):
    PENDING = 10
    RUNNING = 20
    SUCCEEDED = 30
    FAILED = 40
    CANCELLED = 50


class JobStage(str, Enum):
    parse = "parse"
    chunk = "chunk"
    embed = "embed"
    index_es = "index_es"
    index_milvus = "index_milvus"
    commit = "commit"


class JobEventLevel(str, Enum):
    info = "info"
    warn = "warn"
    error = "error"


class RagSpace(DomainModel):
    kb_space: str
    display_name: str
    description: Optional[str] = None

    enabled: bool = True
    status: int = int(SpaceStatus.ENABLED)

    created_at: int = Field(default_factory=now_ts)
    updated_at: int = Field(default_factory=now_ts)


class RagDocument(DomainModel):
    document_id: int
    kb_space: str

    filename: str
    content_type: str
    size: int

    storage_uri: str
    sha256: str

    status: int = int(DocumentStatus.UPLOADED)
    uploader_user_id: int

    active_index_version: Optional[int] = None
    last_error: Optional[str] = None

    created_at: int = Field(default_factory=now_ts)
    updated_at: int = Field(default_factory=now_ts)
    deleted_at: Optional[int] = None


class RagChunk(DomainModel):
    chunk_id: int
    kb_space: str
    document_id: int

    index_version: int
    chunk_index: int

    content: str
    meta: Optional[Dict[str, Any]] = None

    created_at: int = Field(default_factory=now_ts)
    updated_at: int = Field(default_factory=now_ts)


class IngestJob(DomainModel):
    job_id: int
    kb_space: str
    document_id: int

    pipeline_version: int = 1
    idempotency_key: str = ""

    status: int = int(JobStatus.PENDING)
    attempts: int = 0
    max_attempts: int = 3

    lease_owner: Optional[str] = None
    lease_expire_at: Optional[int] = None

    last_error: Optional[str] = None
    created_at: int = Field(default_factory=now_ts)
    updated_at: int = Field(default_factory=now_ts)


class JobEvent(DomainModel):
    job_id: int
    document_id: int
    kb_space: str

    stage: JobStage
    level: JobEventLevel = JobEventLevel.info

    message: str
    data: Optional[Dict[str, Any]] = None

    created_at: int = Field(default_factory=now_ts)


class JobResultStatus(IntEnum):
    SUCCEEDED = 1  # 本次执行成功
    RETRYABLE = 2  # 本次执行失败但可重试（例如第三方解析暂时失败）
    FAILED = 3  # 本次执行失败且不建议重试（例如文件格式不支持）


class JobRunResult(DomainModel):
    """
    worker 一次执行尝试的结果封装
    """
    job_id: int
    document_id: int
    kb_space: str

    status: JobResultStatus
    message: str = ""
    data: Optional[Dict[str, Any]] = None


class SearchRequest(DomainModel):
    kb_space: str = "default"
    query: str
    top_k: int = 10


class SearchHit(DomainModel):
    chunk_id: str  # chunk_id 在 DB 中是 int；对外统一用 str，避免前端/语言差异带来的溢出或精度问题
    document_id: int
    kb_space: str

    index_version: int
    content: str
    meta: Optional[Dict[str, Any]] = None

    score: float


class SearchResponse(DomainModel):
    kb_space: str
    query: str
    top_k: int
    backend: str
    hits: List[SearchHit]
