# -*- coding: utf-8 -*-
# @File: manager.py
# @Author: yaccii
# @Time: 2025-12-11 09:09
# @Description:
# -*- coding: utf-8 -*-
# @File: infrastructure/storage/manager.py
from __future__ import annotations

from typing import Optional, Dict
from fastapi import UploadFile

from infrastructure.config import settings
from .base import FileStorageBackend
from .impl_local import LocalFileStorageBackend
from .impl_s3 import S3FileStorageBackend


class FileStorageManager:
    _instances: Dict[str, FileStorageBackend] = {}

    @classmethod
    def get_backend(cls, kind: Optional[str] = None) -> FileStorageBackend:
        k = (kind or getattr(settings, "file_storage_backend", "local") or "local").lower()
        if k in cls._instances:
            return cls._instances[k]
        if k == "local":
            inst: FileStorageBackend = LocalFileStorageBackend()
        elif k == "s3":
            inst = S3FileStorageBackend()
        else:
            raise ValueError(f"unsupported file_storage_backend: {k}")
        cls._instances[k] = inst
        return inst

    # 便捷函数（保持你现有的函数式调用风格）
    @classmethod
    async def save_upload_file(cls, user_id: int, upload: UploadFile):
        return await cls.get_backend().save_upload_file(user_id, upload)

    @classmethod
    def open_file_by_relative(cls, rel_path: str) -> bytes:
        return cls.get_backend().open_file_by_relative(rel_path)

    @classmethod
    def delete_file_by_relative(cls, rel_path: str) -> None:
        cls.get_backend().delete_file_by_relative(rel_path)
