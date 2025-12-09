# -*- coding: utf-8 -*-
# @File: file_storage.py
# @Author: yaccii
# @Description:
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from fastapi import UploadFile

from infrastructure import mlogger
from .path_utils import (
    build_file_url,
    build_user_file_path,
    relative_to_root,
    resolve_from_relative,
)


async def save_upload_file(user_id: int, upload: UploadFile) -> Tuple[str, str]:
    """
    保存上传文件到本地磁盘。
    返回: (relative_path, public_url)
    """
    target_path: Path = build_user_file_path(user_id, upload.filename or "file")
    content = await upload.read()

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(content)
    except Exception as e:
        mlogger.exception(
            "FileStorage",
            "save_upload_file_error",
            user_id=user_id,
            filename=upload.filename,
            error=str(e),
        )
        raise

    rel_path = relative_to_root(target_path)
    url = build_file_url(rel_path)

    mlogger.info(
        "FileStorage",
        "save_upload_file",
        user_id=user_id,
        rel_path=rel_path,
        url=url,
        size=len(content),
    )
    return rel_path, url


def open_file_by_relative(rel_path: str) -> bytes:
    path = resolve_from_relative(rel_path)
    with open(path, "rb") as f:
        return f.read()


def delete_file_by_relative(rel_path: str) -> None:
    path = resolve_from_relative(rel_path)
    try:
        if path.exists():
            os.remove(path)
            mlogger.info("FileStorage", "delete_file", rel_path=rel_path)
    except Exception as e:
        mlogger.exception(
            "FileStorage",
            "delete_file_error",
            rel_path=rel_path,
            error=str(e),
        )
