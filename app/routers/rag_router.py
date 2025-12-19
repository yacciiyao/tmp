# -*- coding: utf-8 -*-
# @File: rag_router.py

from __future__ import annotations

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, File, UploadFile, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_admin
from domains.error_domain import AppError
from domains.rag_domain import SearchRequest, SearchResponse
from infrastructures.vconfig import config
from infrastructures.db.orm.orm_deps import get_db
from infrastructures.db.repository.rag_repository import RagRepository
from infrastructures.storage.local_storage import LocalStorage
from services.rag.rag_service import RagService
from services.rag.search_service import SearchService
from infrastructures.embedding.embedder_router import create_embedder
from infrastructures.index.index_router import create_es_index, create_milvus_index


router = APIRouter(prefix="/rag", tags=["rag"])

_repo = RagRepository()
_storage = LocalStorage(base_dir=config.storage_dir)
_service = RagService(repo=_repo, storage=_storage)

_search_service: Optional[SearchService] = None


def _get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService(
            repo=_repo,
            embedder=create_embedder(),
            milvus_index=create_milvus_index(),
            es_index=create_es_index(),
        )
    return _search_service


class SpaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kb_space: str
    display_name: str
    description: Optional[str] = None
    enabled: int
    status: int
    created_at: int
    updated_at: int


class SpaceCreateRequest(BaseModel):
    kb_space: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)


class SpaceUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    enabled: Optional[int] = Field(default=None, ge=0, le=1)
    status: Optional[int] = Field(default=None)


@router.post("/spaces", response_model=SpaceResponse)
async def create_space(
    body: SpaceCreateRequest,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> SpaceResponse:
    existing = await _repo.get_space(db, kb_space=body.kb_space)
    if existing is not None:
        raise AppError(code="rag.space_exists", message="Space already exists", http_status=400)

    space = await _repo.create_space(
        db,
        kb_space=body.kb_space,
        display_name=body.display_name,
        description=body.description,
        enabled=1,
        status=1,
    )
    return SpaceResponse.model_validate(space)


@router.get("/spaces", response_model=List[SpaceResponse])
async def list_spaces(
    enabled: Optional[int] = Query(default=None, ge=0, le=1),
    status: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> List[SpaceResponse]:
    spaces = await _repo.list_spaces(db, enabled=enabled, status=status, limit=limit, offset=offset)
    return [SpaceResponse.model_validate(x) for x in spaces]


@router.patch("/spaces/{kb_space}")
async def update_space(
    kb_space: str,
    body: SpaceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> Dict[str, Any]:
    rows = await _repo.update_space(
        db,
        kb_space=kb_space,
        display_name=body.display_name,
        description=body.description,
        enabled=body.enabled,
        status=body.status,
    )
    return {"updated": rows}


@router.delete("/spaces/{kb_space}")
async def delete_space(
    kb_space: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> Dict[str, Any]:
    space_rows, doc_rows = await _repo.delete_space_cascade(db, kb_space=kb_space)
    return {"space_updated": space_rows, "documents_deleted": doc_rows}


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: int
    kb_space: str
    filename: str
    content_type: str
    size: int
    storage_uri: str
    sha256: str
    status: int
    uploader_user_id: int
    active_index_version: Optional[int] = None
    last_error: Optional[str] = None
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class UploadResponse(BaseModel):
    document: DocumentResponse
    job_id: int


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    kb_space: str = Query(default="default"),
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
) -> UploadResponse:
    doc, job = await _service.upload_and_create_job(
        db,
        upload_file=file,
        kb_space=kb_space,
        uploader_user_id=int(admin.user_id),
    )
    return UploadResponse(document=DocumentResponse.model_validate(doc), job_id=int(job.job_id))


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> DocumentResponse:
    doc = await _repo.get_document(db, document_id=document_id, include_deleted=False)
    if doc is None:
        raise AppError(code="rag.document_not_found", message="Document not found", http_status=404)
    return DocumentResponse.model_validate(doc)


@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    kb_space: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> List[DocumentResponse]:
    docs = await _repo.list_documents(db, kb_space=kb_space, limit=limit, offset=offset, statuses=None)
    return [DocumentResponse.model_validate(x) for x in docs]


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> Dict[str, Any]:
    await _service.delete_document(db, document_id=document_id)
    return {"deleted": 1}


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: int
    document_id: int
    kb_space: str
    pipeline_version: str
    index_version: int
    idempotency_key: str
    status: int
    try_count: int
    max_retries: int
    locked_by: Optional[str] = None
    locked_until: Optional[int] = None
    last_error: Optional[str] = None
    created_at: int
    updated_at: int


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> JobResponse:
    job = await _repo.get_job(db, job_id=job_id)
    if job is None:
        raise AppError(code="rag.job_not_found", message="Job not found", http_status=404)
    return JobResponse.model_validate(job)


@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(
    kb_space: Optional[str] = Query(default=None),
    document_id: Optional[int] = Query(default=None),
    status: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> List[JobResponse]:
    statuses = [int(status)] if status is not None else None
    jobs = await _repo.list_jobs(
        db,
        kb_space=kb_space,
        document_id=document_id,
        statuses=statuses,
        limit=int(limit),
        offset=int(offset),
    )
    return [JobResponse.model_validate(x) for x in jobs]


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    document_id: int
    kb_space: str
    index_version: int
    chunk_index: int
    modality: str
    locator: Optional[Dict[str, Any]] = None
    content: str
    content_hash: str
    created_at: int


@router.get("/chunks", response_model=List[ChunkResponse])
async def list_chunks(
    document_id: int = Query(...),
    index_version: Optional[int] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> List[ChunkResponse]:
    doc = await _repo.get_document(db, document_id=document_id, include_deleted=False)
    if doc is None:
        raise AppError(code="rag.document_not_found", message="Document not found", http_status=404)

    ver = index_version
    if ver is None:
        ver = doc.active_index_version
        if ver is None:
            return []

    chunks = await _repo.list_chunks(db, document_id=document_id, index_version=int(ver), limit=limit, offset=offset)
    return [ChunkResponse.model_validate(x) for x in chunks]


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> SearchResponse:
    return await _get_search_service().search(db, req=body)
