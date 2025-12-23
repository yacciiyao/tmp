# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, cast

import jwt
from jwt import PyJWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from domains.error_domain import AppError
from domains.user_domain import UserRole
from infrastructures.db.orm.user_orm import MetaUsersORM
from infrastructures.db.repository.user_repository import UserRepository
from infrastructures.vconfig import vconfig
from infrastructures.vlogger import vlogger

_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class AuthService:
    def __init__(self) -> None:
        self._secret_key: str = vconfig.jwt_secret_key
        self._algorithm: str = vconfig.jwt_algorithm
        self._access_token_expires_minutes: int = int(vconfig.jwt_expire_minutes)

        self._default_admin_username: str = vconfig.default_admin_username
        self._default_admin_password: str = vconfig.default_admin_password

        self._user_repo = UserRepository()

    @staticmethod
    def hash_password(password: str) -> str:
        return _pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, password_hash: str) -> bool:
        return _pwd_context.verify(plain_password, password_hash)

    def _create_token(self, subject: str, extra_claims: Optional[Dict[str, Any]] = None) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self._access_token_expires_minutes)
        to_encode: Dict[str, Any] = {"sub": subject, "iat": int(now.timestamp()), "exp": int(expire.timestamp())}
        if extra_claims:
            to_encode.update(extra_claims)
        return jwt.encode(to_encode, self._secret_key, algorithm=self._algorithm)

    def decode_token(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except PyJWTError as exc:
            raise AppError(code="auth.invalid_token", message="Invalid or expired token", http_status=401) from exc

    def create_access_token_for_user(self, user: MetaUsersORM) -> str:
        return self._create_token(
            subject=str(user.user_id),
            extra_claims={"user_id": user.user_id, "username": user.username, "role": user.role, "status": user.status},
        )

    async def get_user_by_token(self, db: AsyncSession, token: str) -> MetaUsersORM:
        payload = self.decode_token(token)

        sub = payload.get("sub")
        if not sub:
            raise AppError(code="auth.invalid_token", message="Token payload missing subject", http_status=401)

        try:
            user_id = int(str(sub))
        except ValueError as exc:
            raise AppError(code="auth.invalid_token", message="Invalid token subject", http_status=401) from exc

        user = await self._user_repo.get_by_id(db, user_id)
        if not user or int(user.status) != 1:
            raise AppError(code="auth.user_not_found", message="User not found or inactive", http_status=401)

        return user

    async def authenticate(self, db: AsyncSession, username: str, password: str) -> Optional[MetaUsersORM]:
        user = await self._user_repo.get_by_username(db, username)
        if not user or int(user.status) != 1:
            return None

        pw_hash = cast(str, user.password_hash)
        if not self.verify_password(password, pw_hash):
            return None

        return user

    async def authenticate_or_raise(self, db: AsyncSession, username: str, password: str) -> MetaUsersORM:
        user = await self.authenticate(db=db, username=username, password=password)
        if not user:
            raise AppError(
                code="auth.invalid_credentials",
                message="Invalid username or password",
                http_status=401,
            )
        return user

    async def ensure_default_admin(self, db: AsyncSession) -> None:
        if vconfig.app_env != "dev" and self._default_admin_password == "admin123":
            raise RuntimeError("DEFAULT_ADMIN_PASSWORD must be rotated in non-dev environments.")

        existing = await self._user_repo.get_by_username(db, self._default_admin_username)
        if existing:
            return

        password_hash = self.hash_password(self._default_admin_password)
        user = await self._user_repo.create_user(
            db=db,
            username=self._default_admin_username,
            password_hash=password_hash,
            role=UserRole.admin.value,
            status=1,
        )
        await db.commit()

        vlogger.warning("default admin created username=%s (password not logged)", user.username)
