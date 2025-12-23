# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:
from __future__ import annotations

from infrastructures.storage.local_storage import LocalStorage
from infrastructures.vconfig import vconfig


def get_storage():
    # 业务逻辑：项目当前仅支持本地存储，避免无配置的 S3 代码增加维护成本。
    return LocalStorage(base_dir=vconfig.storage_dir)
