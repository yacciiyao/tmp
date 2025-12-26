# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:
from __future__ import annotations

from infrastructures.storage.local_storage import LocalStorage
from infrastructures.vconfig import vconfig


def get_storage():
    return LocalStorage(base_dir=vconfig.storage_dir)
