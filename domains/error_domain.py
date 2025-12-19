# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description:
from typing import Optional, Any

from fastapi import HTTPException
from pydantic import BaseModel
from starlette import status


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class AppError(Exception):
    def __init__(
            self,
            code: str,
            message: str,
            http_status: int = status.HTTP_400_BAD_REQUEST,
            details: Any | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details
        super().__init__(message)

    def to_http_exception(self) -> HTTPException:
        return HTTPException(
            status_code=self.http_status,
            detail=self.to_response().model_dump(),
        )

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(code=self.code, message=self.message, details=self.details)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", details: Any | None = None):
        super().__init__(
            code="NOT_FOUND",
            message=message,
            http_status=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class PermissionDeniedError(AppError):
    def __init__(self, message: str = "Permission denied", details: Any | None = None):
        super().__init__(
            code="PERMISSION_DENIED",
            message=message,
            http_status=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ValidationAppError(AppError):
    def __init__(self, message: str = "Validation error", details: Any | None = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )
