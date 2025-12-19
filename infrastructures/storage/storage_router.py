# -*- coding: utf-8 -*-
# @File: storage_router.py
# @Author: yaccii
# @Time: 2025-12-19 14:05
# @Description:
# -*- coding: utf-8 -*-
from __future__ import annotations

from infrastructures.storage.local_storage import LocalStorage
from infrastructures.storage.s3_storage import S3Storage
from infrastructures.vconfig import config


def get_storage():
    backend = str(getattr(config, "storage_backend", "local") or "local").strip().lower()
    if backend == "s3":
        return S3Storage(base_dir=config.storage_dir)
    return LocalStorage(base_dir=config.storage_dir)
