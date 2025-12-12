# -*- coding: utf-8 -*-
# @File: base.py
# @Author: yaccii
# @Time: 2025-12-11 09:08
# @Description:
# -*- coding: utf-8 -*-
# @File: infrastructure/storage/base.py
from __future__ import annotations

from typing import Protocol, Tuple
from fastapi import UploadFile


class FileStorageBackend(Protocol):
    async def save_upload_file(self, user_id: int, upload: UploadFile) -> Tuple[str, str]:
        ...

    def open_file_by_relative(self, rel_path: str) -> bytes:
        ...

    def delete_file_by_relative(self, rel_path: str) -> None:
        ...
