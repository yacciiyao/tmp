# -*- coding: utf-8 -*-
# @File: user_repository.py
# @Author: yaccii
# @Description:
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.user import UserRole
from infrastructure.db.models import UserORM


class UserRepository:
    async def get_by_id(self, db: AsyncSession, user_id: int) -> Optional[UserORM]:
        stmt = select(UserORM).where(UserORM.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[UserORM]:
        stmt = select(UserORM).where(UserORM.username == username)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users(self, db: AsyncSession, limit: int = 100) -> Sequence[UserORM]:
        stmt = select(UserORM).order_by(UserORM.id.asc()).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create_user(
        self,
        db: AsyncSession,
        username: str,
        password_hash: str,
        role: UserRole = UserRole.USER,
        is_active: bool = True,
    ) -> UserORM:
        user = UserORM(
            username=username,
            password_hash=password_hash,
            role=role.value,
            is_active=is_active,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user