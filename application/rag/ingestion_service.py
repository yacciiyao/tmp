# -*- coding: utf-8 -*-
# @File: application/rag/ingestion_service.py
# @Author: yaccii
# @Description: RAG 文档入库流水线（解析 -> 切分 -> 向量库 -> ES）

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import inspect

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure import mlogger
from infrastructure.rag.loader import load_content
from infrastructure.rag.splitter import split_text
from infrastructure.rag.embeddings import EmbeddingEngine
from infrastructure.vector_store import VectorStoreManager
from infrastructure.search.es_client import ESClient
from infrastructure.repositories.rag_repository import RAGRepository
from infrastructure.llm.llm_registry import LLMRegistry
from infrastructure.db.models import rag_orm as rag_models


@dataclass
class ChunkInput:
    """
    预留给未来多模态的统一入口：
    目前文本文档就用 text + meta={} 即可；
    后续 image/audio/video 可以在 meta 里加位置信息。
    """
    text: str
    meta: Dict[str, Any]


class IngestionResult(BaseModel):
    """
    文档入库结果（返回给后台接口 / 测试脚本）
    """
    doc_id: int
    corpus_id: int
    num_chunks: int
    embedding_alias: str
    vector_store_type: str
    es_index: Optional[str]


class IngestionService:
    """
    RAG 文档入库流水线：
    - 只面向后台导入的 rag_document（source_type=file/url/text）
    - 不处理用户对话中的临时上传（那一块属于 chat 业务）
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.rag_repo = RAGRepository(db)
        self.vector_store_manager = VectorStoreManager()  # 默认 faiss
        self.es_client = ESClient()

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    async def ingest_document(self, doc_id: int) -> IngestionResult:
        """
        文档入库主流程：
        1. 获取文档 & 知识库配置
        2. 解析内容 -> ChunkInput 列表
        3. 写 rag_chunk
        4. 计算向量并写入向量库
        5. 写 ES（BM25）
        6. 更新文档状态
        """
        # ---------------------------
        # 1. 取文档 & 知识库配置
        # ---------------------------
        doc = await self.rag_repo.get_document(doc_id)
        if not doc:
            raise ValueError(f"document not found, id={doc_id}")

        corpus = await self.rag_repo.get_corpus(doc.corpus_id)
        if not corpus:
            raise ValueError(f"corpus not found, id={doc.corpus_id}")

        if not corpus.is_active:
            raise RuntimeError(f"corpus is not active, id={corpus.id}")

        if not corpus.default_embedding_alias:
            raise RuntimeError(
                f"corpus {corpus.id} 未配置 default_embedding_alias，"
                f"请在后台设置后再执行入库"
            )

        embedding_alias = corpus.default_embedding_alias
        vector_store_type = corpus.vector_store_type or "faiss"
        es_index = corpus.es_index  # 允许为 None，由 ESClient 用默认前缀 + corpus_id 生成

        mlogger.info(
            "RAGIngestion",
            "ingest_document:start",
            doc_id=doc.id,
            corpus_id=corpus.id,
            source_type=doc.source_type,
            source_uri=doc.source_uri,
            embedding_alias=embedding_alias,
            vector_store_type=vector_store_type,
            es_index=es_index,
        )

        # ---------------------------
        # 2. 解析内容 -> ChunkInput 列表
        # ---------------------------
        try:
            chunks_input = await self._extract_chunks(doc, corpus)
        except Exception as e:
            await self._mark_failed(doc_id, f"extract_chunks error: {e}")
            raise

        if not chunks_input:
            await self._mark_failed(doc_id, "no chunks after extract")
            raise RuntimeError("no chunks after extract")

        # ---------------------------
        # 3. 写 rag_chunk（先不填 vector_id）
        # ---------------------------
        chunk_orms: List[rag_models.RAGChunkORM] = []
        try:
            for idx, c in enumerate(chunks_input):
                orm = rag_models.RAGChunkORM(
                    corpus_id=corpus.id,
                    doc_id=doc.id,
                    chunk_index=idx,
                    text=c.text,
                    meta=c.meta or {},
                    vector_id=None,  # 稍后回写
                )
                self.db.add(orm)
                chunk_orms.append(orm)

            # flush 拿到 chunk.id
            await self.db.flush()
        except Exception as e:
            await self._mark_failed(doc_id, f"create chunks error: {e}")
            raise

        chunk_ids = [c.id for c in chunk_orms]

        # ---------------------------
        # 4. 计算向量 + 写向量库
        # ---------------------------
        try:
            # 4.1 从 LLMRegistry 里拿 embedding 模型对应的 client
            llm_registry = LLMRegistry()

            # 兼容 sync / async 的 get_client 实现
            client_or_coro = getattr(llm_registry, "get_client", None)
            if client_or_coro is None:
                raise RuntimeError("LLMRegistry 缺少 get_client 方法，无法获取 embedding client")

            client_or_coro = llm_registry.get_client(embedding_alias)  # type: ignore[call-arg]
            if inspect.isawaitable(client_or_coro):
                embed_client = await client_or_coro
            else:
                embed_client = client_or_coro

            if embed_client is None:
                raise RuntimeError(f"无法根据 alias={embedding_alias} 获取 embedding client")

            engine = EmbeddingEngine(embed_client)

            # 4.2 计算向量
            texts = [c.text for c in chunks_input]
            embeddings = await engine.embed_documents(texts)
            if len(embeddings) != len(chunk_orms):
                await self._mark_failed(
                    doc_id,
                    "embedding count mismatch with chunks",
                )
                raise RuntimeError("embedding count mismatch with chunks")

            # 4.3 写向量库
            store = self.vector_store_manager.get_store(vector_store_type)
            metadatas: List[Dict[str, Any]] = []
            for orm in chunk_orms:
                metadatas.append(
                    {
                        "corpus_id": corpus.id,
                        "doc_id": doc.id,
                        "chunk_id": orm.id,
                    }
                )

            vector_ids = await store.add_embeddings(
                corpus_id=corpus.id,
                doc_id=doc.id,
                chunk_ids=chunk_ids,
                embeddings=embeddings,
                metadatas=metadatas,
            )

            if len(vector_ids) != len(chunk_orms):
                await self._mark_failed(
                    doc_id,
                    "vector_ids count mismatch with chunks",
                )
                raise RuntimeError("vector_ids count mismatch with chunks")

            # 回写 vector_id
            for orm, vid in zip(chunk_orms, vector_ids):
                orm.vector_id = vid

        except Exception as e:
            await self._mark_failed(doc_id, f"vector store error: {e}")
            raise

        # ---------------------------
        # 5. 写入 ES（BM25）
        # ---------------------------
        try:
            docs_for_es: List[Dict[str, Any]] = []
            for orm in chunk_orms:
                docs_for_es.append(
                    {
                        "id": orm.id,
                        "doc_id": orm.doc_id,
                        "chunk_id": orm.id,
                        "text": orm.text,
                        "meta": orm.meta or {},
                    }
                )

            await self.es_client.index_chunks(
                index=es_index,
                corpus_id=corpus.id,
                docs=docs_for_es,
                refresh=True,
            )
        except Exception as e:
            # ES 失败视为“降级”：记日志，但不算入库失败
            mlogger.warning(
                "RAGIngestion",
                "es_index",
                msg=f"ES index error: {e}",
                doc_id=doc.id,
                corpus_id=corpus.id,
            )

        # ---------------------------
        # 6. 更新文档状态
        # ---------------------------
        await self.rag_repo.update_document_status(
            doc_id=doc.id,
            status="ingested",
            error_msg=None,
            num_chunks=len(chunk_orms),
        )
        await self.db.commit()

        mlogger.info(
            "RAGIngestion",
            "ingest_document:done",
            doc_id=doc.id,
            corpus_id=corpus.id,
            num_chunks=len(chunk_orms),
        )

        return IngestionResult(
            doc_id=doc.id,
            corpus_id=corpus.id,
            num_chunks=len(chunk_orms),
            embedding_alias=embedding_alias,
            vector_store_type=vector_store_type,
            es_index=es_index,
        )

    # ------------------------------------------------------------------
    # 抽取 Chunk（目前只支持文本类，后面扩多模态就增这里）
    # ------------------------------------------------------------------

    async def _extract_chunks(
        self,
        doc: rag_models.RAGDocumentORM,
        corpus: rag_models.RAGCorpusORM,
    ) -> List[ChunkInput]:
        """
        统一抽象：
        - 未来 image/audio/video 都从这里分流
        - 当前实现：file/url/text -> load_content -> split_text
        """
        source_type = (doc.source_type or "").lower()

        # 目前处理文本类：file/url/text
        if source_type in {"file", "url", "text"}:
            raw_text = await load_content(
                source_type=doc.source_type,
                source_uri=doc.source_uri,
                mime_type=doc.mime_type,
                extra_meta=doc.extra_meta,
            )
            if not raw_text or not raw_text.strip():
                return []

            pieces = split_text(raw_text)
            return [ChunkInput(text=p, meta={}) for p in pieces]

        # 其他类型暂未实现（image/audio/video）
        raise RuntimeError(f"暂不支持的 source_type: {doc.source_type}")

    # ------------------------------------------------------------------
    # 失败标记
    # ------------------------------------------------------------------

    async def _mark_failed(self, doc_id: int, msg: str) -> None:
        """
        入库失败时更新文档状态。
        """
        mlogger.warning(
            "RAGIngestion",
            "ingest_document:failed",
            doc_id=doc_id,
            error=msg,
        )
        try:
            await self.rag_repo.update_document_status(
                doc_id=doc_id,
                status="failed",
                error_msg=msg,
                num_chunks=None,
            )
            await self.db.commit()
        except Exception as e:  # pragma: no cover
            mlogger.warning(
                "RAGIngestion",
                "_mark_failed",
                msg=f"update status error: {e}",
                doc_id=doc_id,
            )
