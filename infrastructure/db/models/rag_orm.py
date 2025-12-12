# -*- coding: utf-8 -*-
# @File: infrastructure/db/models/rag_orm.py
# @Description: RAG ORM（Corpus/Document/Chunk）
from __future__ import annotations

import enum
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, JSON, Enum, Index
from sqlalchemy.orm import relationship

from infrastructure.db.base import Base, TimestampMixin


class RAGDocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class RAGCorpusORM(TimestampMixin, Base):
    __tablename__ = "rag_corpus"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    type = Column(String(50), nullable=False, default="file")
    description = Column(Text, nullable=True)

    # 归属管理员（当前无租户/权限，但记录来源，便于审计/过滤）
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    default_embedding_alias = Column(String(128), nullable=True)
    vector_store_type = Column(String(50), nullable=True)
    es_index = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True, index=True)

    documents = relationship(
        "RAGDocumentORM",
        back_populates="corpus",
        cascade="all, delete-orphan",
        passive_deletes=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RAGCorpusORM id={self.id} name={self.name} owner_id={self.owner_id}>"


class RAGDocumentORM(TimestampMixin, Base):
    __tablename__ = "rag_document"

    id = Column(Integer, primary_key=True, autoincrement=True)

    corpus_id = Column(Integer, ForeignKey("rag_corpus.id"), nullable=False, index=True)

    # 归属管理员（与 Corpus.owner_id 同维度；允许为空以兼容旧数据）
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # 历史字段：上传者（保留以兼容旧逻辑；通常与 owner_id 相同）
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    source_type = Column(String(50), nullable=False, default="file")  # file/url/text/...
    source_uri = Column(String(1024), nullable=False)
    file_name = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)

    status = Column(Enum(RAGDocumentStatus), nullable=False, default=RAGDocumentStatus.PENDING)
    error_msg = Column(Text, nullable=True)
    num_chunks = Column(Integer, default=0)

    extra_meta_json = Column(JSON, nullable=True)

    is_active = Column(Boolean, default=True, index=True)

    corpus = relationship("RAGCorpusORM", back_populates="documents")

    chunks = relationship(
        "RAGChunkORM",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=False,
    )

    @property
    def extra_meta(self):
        return self.extra_meta_json or {}

    @extra_meta.setter
    def extra_meta(self, value):
        self.extra_meta_json = value

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RAGDocumentORM id={self.id} corpus_id={self.corpus_id} status={self.status}>"


# 为了快速按 (corpus_id, file_name) 或 (corpus_id, source_uri) 去重/查找旧版本
Index("ix_corpus_file", RAGDocumentORM.corpus_id, RAGDocumentORM.file_name)
Index("ix_corpus_uri", RAGDocumentORM.corpus_id, RAGDocumentORM.source_uri)


class RAGChunkORM(TimestampMixin, Base):
    __tablename__ = "rag_chunk"

    id = Column(Integer, primary_key=True, autoincrement=True)

    corpus_id = Column(Integer, ForeignKey("rag_corpus.id"), nullable=False, index=True)
    doc_id = Column(Integer, ForeignKey("rag_document.id", ondelete="CASCADE"), nullable=False, index=True)

    chunk_index = Column(Integer, nullable=False, index=True)
    text = Column(Text, nullable=False)

    meta_json = Column(JSON, nullable=True)

    # 向量库内的向量 ID（FAISS 内存实现/ Milvus PK）
    vector_id = Column(Integer, nullable=True, index=True)

    is_active = Column(Boolean, default=True, index=True)

    document = relationship("RAGDocumentORM", back_populates="chunks")

    @property
    def meta(self):
        return self.meta_json or {}

    @meta.setter
    def meta(self, value):
        self.meta_json = value

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RAGChunkORM id={self.id} doc_id={self.doc_id} chunk_index={self.chunk_index}>"
