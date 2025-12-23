# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import hashlib
import os
import re
import time
from typing import Optional

from domains.error_domain import AppError
from infrastructures.storage.storage_base import Storage, StoredFile, UploadFileLike
from infrastructures.vconfig import vconfig

_filename_re = re.compile(r"[^0-9A-Za-z._-]+")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "file").strip() or "file"
    base = _filename_re.sub("_", base)
    if base in {".", ".."}:
        base = "file"
    return base[:180]


class LocalStorage(Storage):
    def __init__(self, *, base_dir: str) -> None:
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    async def save_upload(
            self,
            *,
            kb_space: str,
            uploader_user_id: int,
            upload_file: UploadFileLike,
    ) -> StoredFile:
        # 业务逻辑：只做最小属性检查，避免 UploadFile 的导入路径差异导致误判。
        if not hasattr(upload_file, "read") or not hasattr(upload_file, "close"):
            raise AppError(code="INVALID_UPLOAD", message="upload_file missing read/close")

        filename = getattr(upload_file, "filename", None) or "file"
        content_type = getattr(upload_file, "content_type", None) or "application/octet-stream"

        safe_name = _safe_filename(filename)
        day = time.strftime("%Y%m%d", time.localtime())
        ts_ms = _now_ms()

        rel_dir = os.path.join(str(kb_space), str(int(uploader_user_id)), day)
        abs_dir = os.path.join(self.base_dir, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)

        abs_path = os.path.join(abs_dir, f"{ts_ms}_{safe_name}")

        max_bytes = int(vconfig.max_upload_mb) * 1024 * 1024

        h = hashlib.sha256()
        size = 0

        with open(abs_path, "wb") as f:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                size += len(chunk)
                if size > max_bytes:
                    f.close()
                    os.remove(abs_path)
                    raise AppError(
                        code="upload.too_large",
                        message=f"File exceeds max_upload_mb={int(vconfig.max_upload_mb)}MB",
                        http_status=413,
                        details={"max_upload_mb": int(vconfig.max_upload_mb)},
                    )

        await upload_file.close()

        storage_uri = "local:" + abs_path
        return StoredFile(
            storage_uri=storage_uri,
            filename=filename,
            content_type=content_type,
            size=int(size),
            sha256=h.hexdigest(),
            local_path=abs_path,
        )

    async def resolve_local_path(self, *, storage_uri: str) -> Optional[str]:
        if storage_uri.startswith("local:"):
            return storage_uri[len("local:"):]
        return None
