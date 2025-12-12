# -*- coding: utf-8 -*-
# @File: impl_local.py
# @Author: yaccii
# @Time: 2025-12-11 09:08
# @Description:
# -*- coding: utf-8 -*-
# @File: infrastructure/storage/impl_local.py
from __future__ import annotations

from typing import Tuple
from fastapi import UploadFile
from infrastructure import mlogger
from .path_utils import (
    build_file_url,
    build_user_file_path,
    ensure_root_dir,
    relative_to_root,
    resolve_from_relative,
)
from .base import FileStorageBackend


class LocalFileStorageBackend(FileStorageBackend):
    async def save_upload_file(self, user_id: int, upload: UploadFile) -> Tuple[str, str]:
        target_path = build_user_file_path(user_id, upload.filename or "file")
        ensure_root_dir()
        try:
            with open(target_path, "wb") as f:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception as e:
            mlogger.exception("LocalStorage", "save_fail", path=str(target_path), error=str(e))
            raise
        rel_path = relative_to_root(target_path)
        url = build_file_url(rel_path)
        mlogger.info("LocalStorage", "save_ok", rel_path=rel_path, url=url)
        return rel_path, url

    def open_file_by_relative(self, rel_path: str) -> bytes:
        path = resolve_from_relative(rel_path)
        with open(path, "rb") as f:
            return f.read()

    def delete_file_by_relative(self, rel_path: str) -> None:
        try:
            path = resolve_from_relative(rel_path)
            if path.exists():
                path.unlink(missing_ok=True)
                mlogger.info("LocalStorage", "delete_ok", rel_path=rel_path)
        except Exception as e:
            mlogger.exception("LocalStorage", "delete_fail", rel_path=rel_path, error=str(e))
