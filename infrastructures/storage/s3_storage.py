# -*- coding: utf-8 -*-
# @File: s3_storage.py
# @Author: yaccii
# @Time: 2025-12-19 14:05
# @Description:
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from fastapi import UploadFile

from domains.error_domain import AppError
from infrastructures.storage.storage_base import Storage, StoredFile
from infrastructures.vconfig import config

_filename_re = re.compile(r"[^0-9A-Za-z._-]+")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _sanitize_filename(name: str) -> str:
    name = (name or "").strip() or "file"
    name = _filename_re.sub("_", name)
    if len(name) > 200:
        name = name[-200:]
    return name


def _join_key(prefix: str, *parts: str) -> str:
    p = (prefix or "").strip().strip("/")
    items = [x.strip().strip("/") for x in parts if (x or "").strip().strip("/")]
    if p:
        return "/".join([p] + items)
    return "/".join(items)


def _parse_s3_uri(uri: str) -> Tuple[str, str]:
    # supports: s3://bucket/key
    if uri.startswith("s3://"):
        rest = uri[len("s3://") :]
        bucket, _, key = rest.partition("/")
        if not bucket or not key:
            raise ValueError("invalid s3 uri")
        return bucket, key
    # supports: s3:bucket:key
    if uri.startswith("s3:"):
        rest = uri[len("s3:") :]
        bucket, _, key = rest.partition(":")
        if not bucket or not key:
            raise ValueError("invalid s3 uri")
        return bucket, key
    raise ValueError("invalid s3 uri")


@dataclass(frozen=True)
class _S3Config:
    bucket: str
    region: str
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    session_token: str
    prefix: str
    public_base_url: str


class S3Storage(Storage):
    """S3-backed storage.

    - save_upload uploads file to S3 and returns storage_uri as s3://bucket/key
    - resolve_local_path downloads object to local cache for parsers that need a path
    """

    def __init__(self, *, base_dir: str) -> None:
        self.base_dir = str(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

        c = _S3Config(
            bucket=str(config.s3_bucket or "").strip(),
            region=str(config.s3_region or "").strip(),
            endpoint_url=str(config.s3_endpoint_url or "").strip(),
            access_key_id=str(config.s3_access_key_id or "").strip(),
            secret_access_key=str(config.s3_secret_access_key or "").strip(),
            session_token=str(config.s3_session_token or "").strip(),
            prefix=str(config.s3_prefix or "").strip(),
            public_base_url=str(config.s3_public_base_url or "").strip(),
        )
        if not c.bucket:
            raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")

        self._cfg = c
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            import boto3  # type: ignore
        except Exception as e:
            raise RuntimeError("boto3 is required for S3 storage backend") from e

        kwargs = {}
        if self._cfg.region:
            kwargs["region_name"] = self._cfg.region
        if self._cfg.endpoint_url:
            kwargs["endpoint_url"] = self._cfg.endpoint_url
        if self._cfg.access_key_id and self._cfg.secret_access_key:
            kwargs["aws_access_key_id"] = self._cfg.access_key_id
            kwargs["aws_secret_access_key"] = self._cfg.secret_access_key
        if self._cfg.session_token:
            kwargs["aws_session_token"] = self._cfg.session_token

        self._client = boto3.client("s3", **kwargs)
        return self._client

    def _cache_path_for(self, *, bucket: str, key: str) -> str:
        h = hashlib.sha256(f"{bucket}/{key}".encode("utf-8")).hexdigest()
        ext = os.path.splitext(key)[1].lower()
        cache_dir = os.path.join(self.base_dir, "s3_cache")
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, f"{h}{ext}")

    async def save_upload(self, *, kb_space: str, uploader_user_id: int, upload_file: object) -> StoredFile:
        if not isinstance(upload_file, UploadFile):
            raise AppError(code="INVALID_UPLOAD", message="upload_file must be UploadFile")

        filename = _sanitize_filename(upload_file.filename or "file")
        content_type = str(upload_file.content_type or "")

        tmp_dir = os.path.join(self.base_dir, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, f"upload_{_now_ms()}_{filename}")

        h = hashlib.sha256()
        size = 0

        with open(tmp_path, "wb") as f:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                size += len(chunk)

        key = _join_key(
            self._cfg.prefix,
            kb_space,
            str(uploader_user_id),
            str(_now_ms()),
            filename,
        )

        bucket = self._cfg.bucket
        client = self._get_client()

        def _upload() -> None:
            with open(tmp_path, "rb") as f:
                extra = {}
                if content_type:
                    extra["ContentType"] = content_type
                client.put_object(Bucket=bucket, Key=key, Body=f, **extra)

        await asyncio.to_thread(_upload)

        cache_path = self._cache_path_for(bucket=bucket, key=key)
        if not os.path.exists(cache_path):
            try:
                os.replace(tmp_path, cache_path)
            except Exception:
                pass
        else:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        storage_uri = f"s3://{bucket}/{key}"
        return StoredFile(
            storage_uri=storage_uri,
            filename=filename,
            content_type=content_type,
            size=int(size),
            sha256=h.hexdigest(),
            local_path=cache_path if os.path.exists(cache_path) else None,
        )

    async def resolve_local_path(self, *, storage_uri: str) -> Optional[str]:
        s = (storage_uri or "").strip()
        if s.startswith("local:"):
            return s[len("local:") :]

        if not (s.startswith("s3://") or s.startswith("s3:")):
            return None

        try:
            bucket, key = _parse_s3_uri(s)
        except ValueError:
            return None

        cache_path = self._cache_path_for(bucket=bucket, key=key)
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            return cache_path

        client = self._get_client()

        def _download() -> None:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            client.download_file(bucket, key, cache_path)

        await asyncio.to_thread(_download)
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            return cache_path
        return None
