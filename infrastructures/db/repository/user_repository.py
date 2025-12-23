# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 用户数据访问层

from __future__ import annotations

from typing import Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.user_domain import UserRole
from infrastructures.db.orm.user_orm import MetaUsersORM


class UserRepository:
    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> Optional[MetaUsersORM]:
        stmt = select(MetaUsersORM).where(MetaUsersORM.user_id == user_id)
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> Optional[MetaUsersORM]:
        stmt = select(MetaUsersORM).where(MetaUsersORM.username == username)
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def create_user(
            db: AsyncSession,
            username: str,
            password_hash: str,
            role: Union[UserRole, str],
            status: int = 1,
    ) -> MetaUsersORM:
        role_value = role.value if isinstance(role, UserRole) else role

        user = MetaUsersORM(
            username=username,
            password_hash=password_hash,
            role=role_value,
            status=int(status),
        )
        db.add(user)

        await db.flush()
        return user
