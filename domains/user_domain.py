# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:
from __future__ import annotations

from enum import Enum, IntEnum
from pydantic import Field

from domains.domain_base import DomainModel, now_ts


class UserRole(str, Enum):
    user = "user"
    admin = "admin"


class UserStatus(IntEnum):
    DISABLED = 0  # 停用
    ENABLED = 1  # 启用


class User(DomainModel):
    user_id: int
    username: str
    password_hash: str = Field(..., exclude=True, repr=False)

    role: UserRole = UserRole.user
    status: int = int(UserStatus.ENABLED)

    created_at: int = Field(default_factory=now_ts)
    updated_at: int = Field(default_factory=now_ts)
