# -*- coding: utf-8 -*-
# @File: impl_s3.py
# @Author: yaccii
# @Time: 2025-12-11 09:09
# @Description:
# -*- coding: utf-8 -*-
# @File: infrastructure/storage/impl_s3.py
from __future__ import annotations

from typing import Tuple
from fastapi import UploadFile
from infrastructure import mlogger
from infrastructure.config import settings
from .base import FileStorageBackend
from .path_utils import sanitize_filename

_BOTO_CLIENT = None


def _s3_bucket() -> str:
    bucket = getattr(settings, "s3_bucket", None)
    if not bucket:
        raise RuntimeError("S3 backend requires settings.s3_bucket")
    return str(bucket)


def _get_client():
    global _BOTO_CLIENT
    if _BOTO_CLIENT is not None:
        return _BOTO_CLIENT
    try:
        import boto3  # type: ignore
        from botocore.config import Config as BotoConfig  # type: ignore
    except Exception as e:
        raise RuntimeError("S3 backend requested but 'boto3' is not installed") from e

    endpoint_url = getattr(settings, "s3_endpoint_url", None) or None
    region_name = getattr(settings, "s3_region", None) or None
    access_key = getattr(settings, "s3_access_key", None) or None
    secret_key = getattr(settings, "s3_secret_key", None) or None
    path_style = bool(getattr(settings, "s3_use_path_style", True))

    cfg = BotoConfig(s3={"addressing_style": "path" if path_style else "virtual"})
    _BOTO_CLIENT = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region_name,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=cfg,
    )
    return _BOTO_CLIENT


def _key_for(user_id: int, filename: str) -> str:
    safe = sanitize_filename(filename)
    return f"user_{int(user_id)}/{safe}"


def _public_url(key: str) -> str:
    base = getattr(settings, "file_base_url", "") or ""
    if base:
        base = base.rstrip("/")
        return f"{base}/{key.lstrip('/')}"
    return f"s3://{_s3_bucket()}/{key}"


class S3FileStorageBackend(FileStorageBackend):
    async def save_upload_file(self, user_id: int, upload: UploadFile) -> Tuple[str, str]:
        key = _key_for(user_id, upload.filename or "file")
        data = await upload.read()
        try:
            client = _get_client()
            client.put_object(
                Bucket=_s3_bucket(),
                Key=key,
                Body=data,
                ContentType=upload.content_type or "application/octet-stream",
            )
        except Exception as e:
            mlogger.exception("S3Storage", "save_fail", key=key, error=str(e))
            raise
        url = _public_url(key)
        mlogger.info("S3Storage", "save_ok", key=key, url=url)
        return key, url

    def open_file_by_relative(self, rel_path: str) -> bytes:
        try:
            client = _get_client()
            obj = client.get_object(Bucket=_s3_bucket(), Key=rel_path)
            return obj["Body"].read()
        except Exception as e:
            mlogger.exception("S3Storage", "open_fail", key=rel_path, error=str(e))
            raise FileNotFoundError(rel_path)

    def delete_file_by_relative(self, rel_path: str) -> None:
        try:
            client = _get_client()
            client.delete_object(Bucket=_s3_bucket(), Key=rel_path)
            mlogger.info("S3Storage", "delete_ok", key=rel_path)
        except Exception as e:
            mlogger.exception("S3Storage", "delete_fail", key=rel_path, error=str(e))
