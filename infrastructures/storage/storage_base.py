# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:  Storage abstraction (shared by RAG and chat uploads)

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class StoredFile:
    storage_uri: str
    filename: str
    content_type: str
    size: int
    sha256: str

    local_path: Optional[str] = None


class UploadFileLike(Protocol):
    """上传文件最小接口：兼容 FastAPI/Starlette UploadFile。"""

    filename: Optional[str]
    content_type: Optional[str]

    async def read(self, size: int = -1) -> bytes:
        ...

    async def close(self) -> None:
        ...


class Storage(Protocol):
    async def save_upload(
            self,
            *,
            kb_space: str,
            uploader_user_id: int,
            upload_file: UploadFileLike,
    ) -> StoredFile:
        ...

    async def resolve_local_path(self, *, storage_uri: str) -> Optional[str]:
        ...
