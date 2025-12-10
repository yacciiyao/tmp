from __future__ import annotations

from typing import List, Optional, Dict, Any

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from application.file.file_service import FileService
from application.rag.dto import (
    CorpusCreateRequest,
    CorpusUpdateRequest,
    CorpusResponse,
    CorpusListResponse,
    DocumentCreateRequest,
    DocumentResponse,
    DocumentListResponse,
)
from application.rag.ingestion_service import IngestionService
from infrastructure.repositories.rag_repository import RAGRepository


class RAGService:
    """
    业务逻辑层：
    - 做基本校验
    - 调用仓储
    - （可选）协调文件上传 + 文档创建 + 入库
    - 返回 DTO 给 router / 脚本
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = RAGRepository(db)
        # 文档入库流水线（loader → splitter → embedding → vector_store / ES）
        self.ingestion_service = IngestionService(db)
        # 文件上传 / 解析通用服务
        self.file_service = FileService()

    # ---------- Corpus ----------

    async def create_corpus(self, req: CorpusCreateRequest) -> CorpusResponse:
        orm = await self.repo.create_corpus(
            name=req.name,
            type=req.type,
            description=req.description,
            owner_id=req.owner_id,
            default_embedding_alias=req.default_embedding_alias,
            vector_store_type=req.vector_store_type,
            es_index=req.es_index,
            is_active=True,
        )
        await self.db.commit()
        return CorpusResponse.model_validate(orm)

    async def update_corpus(
        self,
        corpus_id: int,
        req: CorpusUpdateRequest,
    ) -> Optional[CorpusResponse]:
        fields: Dict[str, Any] = {}
        if req.name is not None:
            fields["name"] = req.name
        if req.type is not None:
            fields["type"] = req.type
        if req.description is not None:
            fields["description"] = req.description
        if req.is_active is not None:
            fields["is_active"] = req.is_active
        if req.default_embedding_alias is not None:
            fields["default_embedding_alias"] = req.default_embedding_alias
        if req.vector_store_type is not None:
            fields["vector_store_type"] = req.vector_store_type
        if req.es_index is not None:
            fields["es_index"] = req.es_index

        orm = await self.repo.update_corpus(corpus_id, fields)
        await self.db.commit()
        if not orm:
            return None
        return CorpusResponse.model_validate(orm)

    async def get_corpus(self, corpus_id: int) -> Optional[CorpusResponse]:
        orm = await self.repo.get_corpus(corpus_id)
        if not orm:
            return None
        return CorpusResponse.model_validate(orm)

    async def list_corpora(
        self,
        *,
        owner_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> CorpusListResponse:
        orms = await self.repo.list_corpora(
            owner_id=owner_id,
            limit=limit,
            offset=offset,
        )
        items = [CorpusResponse.model_validate(o) for o in orms]
        return CorpusListResponse(items=items)

    # ---------- Document ----------

    async def create_document(
        self,
        corpus_id: int,
        req: DocumentCreateRequest,
    ) -> DocumentResponse:
        # 简单校验：知识库是否存在、是否 active
        corpus = await self.repo.get_corpus(corpus_id)
        if not corpus:
            raise ValueError(f"corpus not found, id={corpus_id}")
        if not corpus.is_active:
            raise RuntimeError(f"corpus is not active, id={corpus_id}")

        orm = await self.repo.create_document(
            corpus_id=corpus_id,
            source_type=req.source_type,
            source_uri=req.source_uri,
            file_name=req.file_name,
            mime_type=req.mime_type,
            extra_meta=req.extra_meta,
        )
        await self.db.commit()
        return DocumentResponse.model_validate(orm)

    async def get_document(self, doc_id: int) -> Optional[DocumentResponse]:
        orm = await self.repo.get_document(doc_id)
        if not orm:
            return None
        return DocumentResponse.model_validate(orm)

    async def list_documents(
        self,
        *,
        corpus_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> DocumentListResponse:
        orms = await self.repo.list_documents_by_corpus(
            corpus_id=corpus_id,
            limit=limit,
            offset=offset,
        )
        items = [DocumentResponse.model_validate(o) for o in orms]
        return DocumentListResponse(items=items)

    # ---------- 上传 + 入库（管理员导入场景） ----------

    async def upload_and_ingest_document(
        self,
        *,
        corpus_id: int,
        uploader_id: int,
        upload: UploadFile,
    ) -> DocumentResponse:
        """
        管理员上传文件并导入指定知识库（RAG）：

        - 校验知识库存在且为 active
        - 使用 FileService 保存文件到本地（RAG 专用目录 / user_id=0）
        - 创建 rag_document 记录（source_type=file, source_uri=绝对路径）
        - 调用 IngestionService.ingest_document 完成解析 / 切分 / 向量化 / ES
        - 返回最新的 DocumentResponse（包含当前状态）

        注意：
        - 仅后台管理接口应调用该方法
        - 用户对话上传不应走此方法（不会写入 rag_* / 向量库）
        """
        # 1. 校验 corpus
        corpus_orm = await self.repo.get_corpus(corpus_id)
        if not corpus_orm:
            raise ValueError(f"corpus not found, id={corpus_id}")
        if not corpus_orm.is_active:
            raise RuntimeError(f"corpus is not active, id={corpus_id}")

        # 2. 保存文件（FileService 负责路径 / 大小 / URL 等）
        file_info = await self.file_service.upload_rag_file(
            corpus_id=corpus_id,
            uploader_id=uploader_id,
            upload=upload,
        )

        # 3. 创建文档记录（复用 create_document 逻辑）
        create_req = DocumentCreateRequest(
            source_type="file",
            source_uri=file_info.absolute_path,  # loader 按绝对路径读取
            file_name=file_info.file_name,
            mime_type=file_info.mime_type,
            extra_meta={
                "rel_path": file_info.rel_path,
                "url": file_info.url,
                "uploader_id": uploader_id,
                "size_bytes": file_info.size_bytes,
            },
        )
        doc = await self.create_document(corpus_id=corpus_id, req=create_req)

        # 4. 执行入库流水线（解析 / 切片 / 向量 / ES）
        await self.ingestion_service.ingest_document(doc_id=doc.id)

        # 5. 返回最新文档状态（包含入库后的 num_chunks / status 等）
        latest = await self.get_document(doc_id=doc.id)
        return latest or doc
