# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: DomainModel 基类与公共工具（统一配置/时间戳）

from __future__ import annotations

import time
from typing import Dict, Any

from pydantic import BaseModel, ConfigDict


def now_ts() -> int:
    return int(time.time())


class DomainModel(BaseModel):
    # 允许字段名包含 model_*（如 model_name），避免 pydantic protected namespace 告警
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    def to_dict(self, *, exclude_none: bool = False) -> Dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=exclude_none)
