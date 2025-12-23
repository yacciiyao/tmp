# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 知识库相关表（空间/文档/入库作业/chunk）

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from infrastructures.db.orm.orm_base import Base, TimestampMixin, now_ts


class SpaceORM(TimestampMixin, Base):
    __tablename__ = "meta_rag_spaces"

    kb_space: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False, comment="业务域code(主键)")
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="展示名")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="描述")

    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="开关：1启用/0停用")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="状态：0停用/1启用")


class DocumentORM(TimestampMixin, Base):
    __tablename__ = "meta_rag_documents"

    document_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="文档ID(自增)")
    kb_space: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("meta_rag_spaces.kb_space"),
        nullable=False,
        comment="业务域",
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False, comment="文件名")
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, comment="MIME类型")
    size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="文件大小(bytes)")

    storage_uri: Mapped[str] = mapped_column(String(1024), nullable=False, comment="存储URI(local:/... 或 s3://...)")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="文件sha256(64hex)")

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        comment="状态：10上传/20处理中/30已索引/40失败/90删除",
    )
    uploader_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meta_users.user_id"),
        nullable=False,
        comment="上传者user_id",
    )

    active_index_version: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="当前可检索版本号")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="最近一次错误信息")

    deleted_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="删除时间戳(秒)")

    __table_args__ = (
        Index("ix_rdoc_space", "kb_space"),
        Index("ix_rdoc_status", "status"),
        Index("ix_rdoc_uploader", "uploader_user_id"),
    )


class IngestJobORM(TimestampMixin, Base):
    __tablename__ = "ops_rag_ingest_jobs"

    job_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="作业ID(自增)")
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meta_rag_documents.document_id"),
        nullable=False,
        comment="文档ID",
    )
    kb_space: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("meta_rag_spaces.kb_space"),
        nullable=False,
        comment="业务域",
    )

    pipeline_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1", comment="pipeline版本")
    index_version: Mapped[int] = mapped_column(Integer, nullable=False, comment="索引版本号")

    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="幂等键(唯一)")

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        comment="状态：10待执行/20执行中/30成功/40失败/50取消",
    )

    try_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已重试次数")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, comment="最大重试次数")

    locked_by: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="锁持有者(worker)")
    locked_until: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="锁过期时间戳(秒)")

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="最近一次错误信息")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_rij_idem"),
        Index("ix_rij_lock", "status", "locked_until"),
        Index("ix_rij_doc", "document_id"),
        Index("ix_rij_space", "kb_space"),
    )


class ChunkORM(Base):
    __tablename__ = "stg_rag_chunks"

    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False, comment="chunk主键(稳定ID)")
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meta_rag_documents.document_id"),
        nullable=False,
        comment="文档ID",
    )
    kb_space: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("meta_rag_spaces.kb_space"),
        nullable=False,
        comment="业务域",
    )

    index_version: Mapped[int] = mapped_column(Integer, nullable=False, comment="索引版本号")
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="chunk序号(从0开始)")

    modality: Mapped[str] = mapped_column(String(16), nullable=False, default="text", comment="类型:text/image/audio/mixed")
    locator: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
        comment="定位信息JSON(page/time_range/bbox等)",
    )

    content: Mapped[str] = mapped_column(Text, nullable=False, comment="chunk内容")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="内容sha256(64hex)")
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="token数(估算)")

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts, comment="创建时间戳(秒)")

    __table_args__ = (
        Index("ix_ck_dv", "document_id", "index_version"),
        Index("ix_ck_sv", "kb_space", "index_version"),
        UniqueConstraint("document_id", "index_version", "chunk_index", name="uq_ck_dvi"),
    )
