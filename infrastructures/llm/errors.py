# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: LLM infrastructure error types (no business logic).

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LlmError(Exception):
    """Base error for LLM infrastructure.

    This is intentionally *not* tied to FastAPI exceptions.
    Infrastructure callers (services/routers) can decide how to map it.
    """

    code: str
    message: str
    retryable: bool = False
    provider: Optional[str] = None
    http_status: int = 400
    details: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code}: {self.message}"


class LlmConfigError(LlmError):
    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="llm.config_error",
            message=message,
            retryable=False,
            http_status=400,
            details=details,
        )


class LlmProviderError(LlmError):
    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        code: str = "llm.provider_error",
        retryable: bool = False,
        http_status: int = 502,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=code,
            message=message,
            retryable=retryable,
            provider=provider,
            http_status=http_status,
            details=details,
        )


class LlmTimeoutError(LlmProviderError):
    def __init__(self, message: str = "LLM request timed out", *, provider: Optional[str] = None):
        super().__init__(
            message,
            provider=provider,
            code="llm.timeout",
            retryable=True,
            http_status=504,
        )


class LlmAuthError(LlmProviderError):
    def __init__(self, message: str = "LLM authentication failed", *, provider: Optional[str] = None):
        super().__init__(
            message,
            provider=provider,
            code="llm.auth_failed",
            retryable=False,
            http_status=401,
        )


class LlmRateLimitError(LlmProviderError):
    def __init__(self, message: str = "LLM rate limited", *, provider: Optional[str] = None):
        super().__init__(
            message,
            provider=provider,
            code="llm.rate_limited",
            retryable=True,
            http_status=429,
        )


class LlmBadRequestError(LlmProviderError):
    def __init__(self, message: str = "LLM bad request", *, provider: Optional[str] = None, details=None):
        super().__init__(
            message,
            provider=provider,
            code="llm.bad_request",
            retryable=False,
            http_status=400,
            details=details,
        )


class LlmUnsupportedModalityError(LlmProviderError):
    def __init__(self, message: str, *, provider: Optional[str] = None, details=None):
        super().__init__(
            message,
            provider=provider,
            code="llm.unsupported_modality",
            retryable=False,
            http_status=400,
            details=details,
        )
