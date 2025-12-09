# -*- coding: utf-8 -*-
# @File: user.py
# @Author: yaccii
# @Description:
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from .base import Entity


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class User(Entity):
    model_config = ConfigDict(from_attributes=True)

    username: str
    password_hash: str
    role: UserRole = UserRole.USER
    is_active: bool = True
    created_at: int = 0
    updated_at: int = 0


class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole = UserRole.USER


class UserPublic(BaseModel):
    id: int
    username: str
    role: UserRole
