# -*- coding: utf-8 -*-
# @File: infrastructure/db/models/rag_orm.py
# @Author: yaccii
# @Description: RAG 相关 ORM：知识库 / 文档 / Chunk

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.base import Base, TimestampMixin


class RAGCorpusORM(TimestampMixin, Base):
    """
    知识库（Corpus）：
    - 逻辑上的一个知识集合，例如 “项目知识库 / 产品说明书 / NAS 文档库”
    - 绑定默认 embedding 模型、向量库类型、ES 索引等
    """
    __tablename__ = "rag_corpus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 基本信息
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="project",  # project / product / faq / nas / other
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 拥有者（后台管理用，可先简单用 user_id）
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # RAG 相关配置
    # - 默认 Embedding 模型的 alias（llm_model.alias）
    default_embedding_alias: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    # - 向量库类型（faiss/milvus/...）
    vector_store_type: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )
    # - ES 索引名（为空则使用 prefix + corpus_id 的默认规则）
    es_index: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    # 关系
    documents: Mapped[list["RAGDocumentORM"]] = relationship(
        "RAGDocumentORM",
        back_populates="corpus",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RAGDocumentORM(TimestampMixin, Base):
    """
    知识库中的一个“原始文档”：
    - 来源可以是 file/url/text 等
    - 入库状态 / 错误信息 / chunk 数量
    """
    __tablename__ = "rag_document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    corpus_id: Mapped[int] = mapped_column(
        ForeignKey("rag_corpus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 来源类型：file/url/text/... （也可以扩展 image/audio/video）
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_uri: Mapped[str] = mapped_column(String(512), nullable=False)

    # 文件信息（若来源为 file）
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # 入库状态：pending / ingesting / ingested / failed
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
    )
    error_msg: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # chunk 统计
    num_chunks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 额外元数据：例如页码信息、上传人、标签等
    extra_meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    # 关系
    corpus: Mapped["RAGCorpusORM"] = relationship(
        "RAGCorpusORM",
        back_populates="documents",
    )
    chunks: Mapped[list["RAGChunkORM"]] = relationship(
        "RAGChunkORM",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RAGChunkORM(TimestampMixin, Base):
    """
    切分后的最小检索单元（Chunk）：
    - text: 可被 embedding 模型处理的文本
    - meta: 用于存储多模态/位置信息（页码/时间段/图片URL等）
    - vector_id: 向量库内部 ID（用于排查/调试）
    """
    __tablename__ = "rag_chunk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    corpus_id: Mapped[int] = mapped_column(
        ForeignKey("rag_corpus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    doc_id: Mapped[int] = mapped_column(
        ForeignKey("rag_document.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 在文档中的顺序
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # 切好的文本内容
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # 元信息：模态 / 页码 / 时间范围 / 原图URL 等
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    # 向量库内部的 ID（Faiss/Milvus 等内部编号）
    vector_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 关系
    document: Mapped["RAGDocumentORM"] = relationship(
        "RAGDocumentORM",
        back_populates="chunks",
    )
