# -*- coding: utf-8 -*-
# @File: infrastructure/storage/file_storage.py
# @Author: yaccii
# @Description: 统一文件存储封装：local 或 s3（按配置）

from __future__ import annotations

from typing import Tuple

from fastapi import UploadFile

from infrastructure import mlogger
from infrastructure.config import settings
from .path_utils import (
    build_file_url,
    build_user_file_path,
    ensure_root_dir,
    relative_to_root,
    resolve_from_relative,
    sanitize_filename,
)

# ------------------------- S3 依赖（可选） -------------------------
_S3_ENABLED = False
_boto3 = None
_BOTO_CLIENT = None

if (getattr(settings, "file_storage_backend", "local") or "local").lower() == "s3":
    try:
        import boto3  # type: ignore
        from botocore.config import Config as BotoConfig  # type: ignore

        _boto3 = boto3
        _S3_ENABLED = True
    except Exception:
        _S3_ENABLED = False  # 非 S3 模式无须安装 boto3


# ------------------------- 公共工具 -------------------------

def _get_backend() -> str:
    return (getattr(settings, "file_storage_backend", "local") or "local").lower()


def _s3_bucket() -> str:
    bucket = getattr(settings, "s3_bucket", None)
    if not bucket:
        raise RuntimeError("S3 backend requires settings.s3_bucket")
    return str(bucket)


def _get_s3_client():
    global _BOTO_CLIENT
    if _BOTO_CLIENT is not None:
        return _BOTO_CLIENT
    if not _S3_ENABLED:
        raise RuntimeError("S3 backend requested but 'boto3' is not installed")

    import boto3  # type: ignore
    from botocore.config import Config as BotoConfig  # type: ignore

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


def _s3_key_for(user_id: int, filename: str) -> str:
    safe = sanitize_filename(filename)
    return f"user_{int(user_id)}/{safe}"


def _compose_s3_public_url(key: str) -> str:
    """
    返回可公开访问的 URL：
      - 若 settings.file_base_url 存在：<base>/<key>
      - 否则返回 s3://<bucket>/<key>
    """
    base = getattr(settings, "file_base_url", "") or ""
    if base:
        base = base.rstrip("/")
        return f"{base}/{key.lstrip('/')}"
    return f"s3://{_s3_bucket()}/{key}"


# ------------------------- 本地后端实现 -------------------------

async def _save_local(user_id: int, upload: UploadFile) -> Tuple[str, str]:
    target_path = build_user_file_path(user_id, upload.filename or "file")
    ensure_root_dir()

    try:
        with open(target_path, "wb") as f:
            while True:
                chunk = await upload.read(1024 * 1024)  # 1MB
                if not chunk:
                    break
                f.write(chunk)
    except Exception as e:
        mlogger.exception("FileStorage", "save_local_fail", path=str(target_path), error=str(e))
        raise

    rel_path = relative_to_root(target_path)
    url = build_file_url(rel_path)
    mlogger.info("FileStorage", "save_local_ok", rel_path=rel_path, url=url)
    return rel_path, url


def _open_local(rel_path: str) -> bytes:
    path = resolve_from_relative(rel_path)
    with open(path, "rb") as f:
        return f.read()


def _delete_local(rel_path: str) -> None:
    try:
        path = resolve_from_relative(rel_path)
        if path.exists():
            path.unlink(missing_ok=True)
            mlogger.info("FileStorage", "delete_local_ok", rel_path=rel_path)
    except Exception as e:
        mlogger.exception("FileStorage", "delete_local_fail", rel_path=rel_path, error=str(e))


# ------------------------- S3 后端实现 -------------------------

async def _save_s3(user_id: int, upload: UploadFile) -> Tuple[str, str]:
    if not _S3_ENABLED:
        raise RuntimeError("S3 backend requested but 'boto3' is not installed")

    key = _s3_key_for(user_id, upload.filename or "file")
    data = await upload.read()
    try:
        client = _get_s3_client()
        client.put_object(
            Bucket=_s3_bucket(),
            Key=key,
            Body=data,
            ContentType=upload.content_type or "application/octet-stream",
        )
    except Exception as e:
        mlogger.exception("FileStorage", "save_s3_fail", key=key, error=str(e))
        raise

    url = _compose_s3_public_url(key)
    mlogger.info("FileStorage", "save_s3_ok", key=key, url=url)
    return key, url


def _open_s3(rel_path: str) -> bytes:
    try:
        client = _get_s3_client()
        obj = client.get_object(Bucket=_s3_bucket(), Key=rel_path)
        return obj["Body"].read()
    except Exception as e:
        mlogger.exception("FileStorage", "open_s3_fail", key=rel_path, error=str(e))
        raise FileNotFoundError(rel_path)


def _delete_s3(rel_path: str) -> None:
    try:
        client = _get_s3_client()
        client.delete_object(Bucket=_s3_bucket(), Key=rel_path)
        mlogger.info("FileStorage", "delete_s3_ok", key=rel_path)
    except Exception as e:
        mlogger.exception("FileStorage", "delete_s3_fail", key=rel_path, error=str(e))


# ------------------------- 统一导出 API -------------------------

async def save_upload_file(user_id: int, upload: UploadFile) -> Tuple[str, str]:
    """
    保存上传文件。
    返回 (rel_path, url)：
      - local: rel_path 为 ROOT 相对路径，url 为 file_base_url/rel_path（或 rel_path）
      - s3:    rel_path 为对象 key，     url 为 file_base_url/key（或 s3://bucket/key）
    """
    backend = _get_backend()
    if backend == "local":
        return await _save_local(user_id, upload)
    if backend == "s3":
        return await _save_s3(user_id, upload)
    raise ValueError(f"unsupported file_storage_backend: {backend}")


def open_file_by_relative(rel_path: str) -> bytes:
    """根据相对路径/对象 key 读取文件内容（返回二进制）。"""
    backend = _get_backend()
    if backend == "local":
        return _open_local(rel_path)
    if backend == "s3":
        return _open_s3(rel_path)
    raise ValueError(f"unsupported file_storage_backend: {backend}")


def delete_file_by_relative(rel_path: str) -> None:
    """删除相对路径/对象 key 对应的文件（忽略不存在）。"""
    backend = _get_backend()
    if backend == "local":
        return _delete_local(rel_path)
    if backend == "s3":
        return _delete_s3(rel_path)
    raise ValueError(f"unsupported file_storage_backend: {backend}")
