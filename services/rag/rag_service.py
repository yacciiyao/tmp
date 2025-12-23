# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: RAG 服务（space/document/job/chunk 的业务编排）

from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from domains.error_domain import AppError
from infrastructures.db.orm.rag_orm import MetaRagSpacesORM, MetaRagDocumentsORM, OpsRagIngestJobsORM, StgRagChunksORM
from infrastructures.db.repository.rag_repository import RagRepository
from infrastructures.storage.storage_base import Storage


class RagService:
    def __init__(self, *, repo: RagRepository, storage: Storage) -> None:
        self.repo = repo
        self.storage = storage

    async def create_space(
            self,
            db: AsyncSession,
            *,
            kb_space: str,
            display_name: str,
            description: Optional[str] = None,
            enabled: int = 1,
            status: int = 1,
    ) -> MetaRagSpacesORM:
        existing = await self.repo.get_space(db, kb_space=kb_space)
        if existing is not None:
            raise AppError(code="rag.space_exists", message="Space already exists", http_status=400)

        return await self.repo.create_space(
            db,
            kb_space=kb_space,
            display_name=display_name,
            description=description,
            enabled=int(enabled),
            status=int(status),
        )

    async def get_space(self, db: AsyncSession, *, kb_space: str) -> MetaRagSpacesORM:
        space = await self.repo.get_space(db, kb_space=kb_space)
        if space is None:
            raise AppError(code="rag.space_not_found", message="Space not found", http_status=404)
        return space

    async def list_spaces(
            self,
            db: AsyncSession,
            *,
            enabled: Optional[int] = None,
            status: Optional[int] = None,
            limit: int = 50,
            offset: int = 0,
    ) -> List[MetaRagSpacesORM]:
        return await self.repo.list_spaces(db, enabled=enabled, status=status, limit=limit, offset=offset)

    async def update_space(
            self,
            db: AsyncSession,
            *,
            kb_space: str,
            display_name: Optional[str] = None,
            description: Optional[str] = None,
            enabled: Optional[int] = None,
            status: Optional[int] = None,
    ) -> int:
        return await self.repo.update_space(
            db,
            kb_space=kb_space,
            display_name=display_name,
            description=description,
            enabled=enabled,
            status=status,
        )

    async def delete_space(self, db: AsyncSession, *, kb_space: str) -> int:
        return await self.repo.delete_space(db, kb_space=kb_space)

    async def delete_space_cascade(self, db: AsyncSession, *, kb_space: str) -> Dict[str, Any]:
        space_rows, doc_rows = await self.repo.delete_space_cascade(db, kb_space=kb_space)
        return {"space_updated": int(space_rows), "documents_deleted": int(doc_rows)}

    async def _require_space_available(self, db: AsyncSession, *, kb_space: str) -> MetaRagSpacesORM:
        space = await self.repo.get_space(db, kb_space=kb_space)
        if space is None:
            raise AppError(code="rag.space_not_found", message="Space not found", http_status=404)
        if int(space.status) != 1 or int(space.enabled) != 1:
            raise AppError(code="rag.space_disabled", message="Space is disabled", http_status=400)
        return space

    async def upload_and_create_job(
            self,
            db: AsyncSession,
            *,
            upload_file: UploadFile,
            kb_space: str = "default",
            uploader_user_id: int,
            pipeline_version: str = "v1",
            max_retries: int = 3,
    ) -> Tuple[MetaRagDocumentsORM, OpsRagIngestJobsORM]:
        await self._require_space_available(db, kb_space=kb_space)

        stored = await self.storage.save_upload(
            kb_space=kb_space,
            uploader_user_id=int(uploader_user_id),
            upload_file=upload_file,
        )

        doc = await self.repo.create_document(
            db,
            kb_space=kb_space,
            filename=stored.filename,
            content_type=stored.content_type,
            size=int(stored.size),
            storage_uri=stored.storage_uri,
            sha256=stored.sha256,
            uploader_user_id=int(uploader_user_id),
        )

        job = await self.repo.create_job_for_document(
            db,
            document_id=int(doc.document_id),
            kb_space=kb_space,
            pipeline_version=pipeline_version,
            max_retries=int(max_retries),
        )

        return doc, job

    async def get_document(self, db: AsyncSession, *, document_id: int,
                           include_deleted: bool = False) -> MetaRagDocumentsORM:
        doc = await self.repo.get_document(db, document_id=document_id, include_deleted=include_deleted)
        if doc is None:
            raise AppError(code="rag.document_not_found", message="Document not found", http_status=404)
        return doc

    async def list_documents(
            self,
            db: AsyncSession,
            *,
            kb_space: Optional[str] = None,
            limit: int = 50,
            offset: int = 0,
    ) -> List[MetaRagDocumentsORM]:
        return await self.repo.list_documents(db, kb_space=kb_space, limit=limit, offset=offset)

    async def update_document_filename(self, db: AsyncSession, *, document_id: int, filename: str) -> int:
        filename = (filename or "").strip()
        if not filename:
            raise AppError(code="rag.filename_invalid", message="filename is required", http_status=400)

        doc = await self.get_document(db, document_id=int(document_id), include_deleted=False)
        if int(getattr(doc, "status", 0)) >= 90:
            raise AppError(code="rag.document_deleted", message="Document is deleted", http_status=400)

        return await self.repo.update_document_filename(db, document_id=int(document_id), filename=filename)

    async def delete_document(self, db: AsyncSession, *, document_id: int) -> int:
        """软删 document + 取消未终态 job（不删除原始文件）"""
        doc = await self.repo.get_document(db, document_id=document_id, include_deleted=True)
        if doc is None:
            raise AppError(code="rag.document_not_found", message="Document not found", http_status=404)

        rows = await self.repo.mark_document_deleted(db, document_id=int(document_id))
        await self.repo.cancel_jobs_by_document(db, document_id=int(document_id), last_error="document deleted")
        return int(rows)

    async def get_job(self, db: AsyncSession, *, job_id: int) -> OpsRagIngestJobsORM:
        job = await self.repo.get_job(db, job_id=job_id)
        if job is None:
            raise AppError(code="rag.job_not_found", message="Job not found", http_status=404)
        return job

    async def list_jobs(
            self,
            db: AsyncSession,
            *,
            kb_space: Optional[str] = None,
            statuses: Optional[List[int]] = None,
            limit: int = 50,
            offset: int = 0,
    ) -> List[OpsRagIngestJobsORM]:
        return await self.repo.list_jobs(db, kb_space=kb_space, statuses=statuses, limit=int(limit), offset=int(offset))

    async def list_chunks(
            self,
            db: AsyncSession,
            *,
            document_id: int,
            index_version: Optional[int] = None,
            limit: int = 200,
            offset: int = 0,
    ) -> List[StgRagChunksORM]:
        doc = await self.get_document(db, document_id=document_id, include_deleted=False)

        ver = index_version
        if ver is None:
            ver = doc.active_index_version
            if ver is None:
                return []

        return await self.repo.list_chunks(
            db,
            document_id=int(document_id),
            index_version=int(ver),
            limit=int(limit),
            offset=int(offset),
        )
