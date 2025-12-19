# -*- coding: utf-8 -*-
# @File: user_repository.py
# @Author: yaccii
# @Description: 用户数据访问层（只做 DB 读写封装，不做业务逻辑）

from __future__ import annotations

from typing import Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.user_domain import UserRole
from infrastructures.db.orm.user_orm import UserORM


class UserRepository:
    async def get_by_id(self, db: AsyncSession, user_id: int) -> Optional[UserORM]:
        stmt = select(UserORM).where(UserORM.user_id == user_id)
        res = await db.execute(stmt)
        return res.scalars().first()

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[UserORM]:
        stmt = select(UserORM).where(UserORM.username == username)
        res = await db.execute(stmt)
        return res.scalars().first()

    async def create_user(
        self,
        db: AsyncSession,
        username: str,
        password_hash: str,
        role: Union[UserRole, str],
        status: int = 1,
    ) -> UserORM:
        role_value = role.value if isinstance(role, UserRole) else role

        user = UserORM(
            username=username,
            password_hash=password_hash,
            role=role_value,
            status=int(status),
        )
        db.add(user)

        # 让自增主键尽快回填（由上层决定是否 commit/rollback）
        await db.flush()
        return user
