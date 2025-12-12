# -*- coding: utf-8 -*-
# @File: auth_service.py
# @Author: yaccii
# @Description: 认证相关服务（密码 / JWT / 默认 admin 初始化）

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, cast

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from application.common.errors import AppError
from domain.user import UserRole
from infrastructure.config import settings
from infrastructure.db.models.user_orm import UserORM
from infrastructure.repositories.user_repository import UserRepository

_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class AuthService:
    """
    负责：
    - 密码哈希 & 校验
    - JWT 生成 & 解析
    - 用户身份校验
    - 默认 admin 初始化
    """

    def __init__(self) -> None:
        self._secret_key: str = settings.jwt_secret_key
        self._algorithm: str = getattr(settings, "jwt_algorithm", "HS256")
        self._access_token_expires_minutes: int = int(
            getattr(settings, "jwt_expire_minutes", 1440)
        )

        # UserRepository 采用“方法传 db”的风格，这里只保留一个实例
        self._user_repo = UserRepository()

        # 默认 admin 账号，从配置 / 环境变量读取，代码里只提供兜底默认值
        # 建议在 .env 或 Settings 里配置：
        # DEFAULT_ADMIN_USERNAME=xxx
        # DEFAULT_ADMIN_PASSWORD=xxx
        self._default_admin_username: str = getattr(
            settings, "default_admin_username", "admin"
        )
        self._default_admin_password: str = getattr(
            settings, "default_admin_password", "admin123"
        )

    # -------- password --------

    def hash_password(self, password: str) -> str:
        return _pwd_context.hash(password)

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        return _pwd_context.verify(plain_password, password_hash)

    # -------- JWT --------

    def _create_token(self, subject: str, extra_claims: Optional[Dict[str, Any]] = None) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self._access_token_expires_minutes)
        to_encode: Dict[str, Any] = {
            "sub": subject,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
        if extra_claims:
            to_encode.update(extra_claims)

        encoded_jwt = jwt.encode(to_encode, self._secret_key, algorithm=self._algorithm)
        return encoded_jwt

    def decode_token(self, token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except JWTError as exc:
            raise AppError(
                code="auth.invalid_token",
                message="Invalid or expired token",
                http_status=401,
            ) from exc
        return payload

    def create_access_token_for_user(self, user: UserORM) -> str:
        return self._create_token(
            subject=str(user.id),
            extra_claims={
                "username": user.username,
                "role": user.role,
            },
        )

    # -------- 用户认证 --------

    async def authenticate(
        self,
        db: AsyncSession,
        username: str,
        password: str,
    ) -> Optional[UserORM]:
        """
        登录校验：
        - 用户存在 & active
        - 密码正确
        """
        user = await self._user_repo.get_by_username(db, username)
        if not user or not user.is_active:
            return None

        # user.password_hash 是 SQLAlchemy 的 Mapped[str]，类型检查会报，
        # 但运行时实际就是 str，这里显式 cast 一下，消除 IDE 噪音。
        pw_hash = cast(str, user.password_hash)

        if not self.verify_password(password, pw_hash):
            return None
        return user

    # -------- 默认 admin 初始化 --------

    async def ensure_default_admin(self, db: AsyncSession) -> None:
        """
        如果不存在 admin 用户，则自动创建一个默认 admin。
        - dev 环境：允许使用默认口令（但不打印明文）
        - 非 dev：必须通过环境变量显式配置 DEFAULT_ADMIN_PASSWORD（否则直接报错阻止启动）
        """
        # 非 dev 环境禁止使用默认口令（避免“上线即裸奔”）
        if settings.app_env != "dev":
            if self._default_admin_password == "admin123":
                raise RuntimeError(
                    "DEFAULT_ADMIN_PASSWORD must be set in non-dev environments."
                )

        existing = await self._user_repo.get_by_username(db, self._default_admin_username)
        if existing:
            return

        password_hash = self.hash_password(self._default_admin_password)
        user = await self._user_repo.create_user(
            db=db,
            username=self._default_admin_username,
            password_hash=password_hash,
            role=UserRole.ADMIN,
            is_active=True,
        )
        await db.commit()

        # 不输出明文密码
        from infrastructure import mlogger
        mlogger.warning(
            "AuthService",
            "default_admin_created",
            msg="default admin user created (password not logged). Please rotate ASAP.",
            username=user.username,
        )
