# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

import time
from typing import Dict, Any

from pydantic import BaseModel, ConfigDict


def now_ts() -> int:
    return int(time.time())


class DomainModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    def to_dict(self, *, exclude_none: bool = False) -> Dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=exclude_none)
