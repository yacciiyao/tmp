# -*- coding: utf-8 -*-
# @File: base.py
# @Author: yaccii
# @Description:
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class Entity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
