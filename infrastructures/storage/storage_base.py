# -*- coding: utf-8 -*-
# @File: storage_base.py
# @Author: yaccii
# @Time: 2025-12-15
# @Description: Storage abstraction (shared by RAG and chat uploads)

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class StoredFile:
    """Result of saving an uploaded file."""

    storage_uri: str
    filename: str
    content_type: str
    size: int
    sha256: str

    # For local storage we can return a filesystem path (for debugging/parser).
    local_path: Optional[str] = None


class Storage(Protocol):
    async def save_upload(
        self,
        *,
        kb_space: str,
        uploader_user_id: int,
        upload_file: object,
    ) -> StoredFile:
        """Persist an UploadFile and return StoredFile.

        upload_file: FastAPI UploadFile (kept as object to avoid hard dependency in this layer).
        """

    async def resolve_local_path(self, *, storage_uri: str) -> Optional[str]:
        """Return local path for a given storage_uri if available."""
