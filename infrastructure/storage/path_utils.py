# -*- coding: utf-8 -*-
# @File: infrastructure/storage/path_utils.py
# @Author: yaccii
# @Description: 本地路径/URL 工具；S3 也复用同样的相对路径规则作为对象 key

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from infrastructure import mlogger
from infrastructure.config import settings

# 本地根目录（仅 local 后端使用）
_ROOT: Path = Path(getattr(settings, "file_storage_root", "./data/files")).resolve()


def ensure_root_dir() -> None:
    """确保本地根目录存在（仅 local 后端有效）。"""
    try:
        _ROOT.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        mlogger.exception("FileStorage", "ensure_root_dir_fail", root=str(_ROOT), error=str(e))
        raise


_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    """仅保留 [A-Za-z0-9._-]，其余替换为 '_'。"""
    filename = filename or "file"
    base = os.path.basename(filename)
    base = _SANITIZE_RE.sub("_", base)
    return base or "file"


def user_upload_dir(user_id: int) -> Path:
    """本地后端用户目录（绝对路径）。"""
    return _ROOT / f"user_{int(user_id)}"


def build_user_file_path(user_id: int, filename: str) -> Path:
    """本地后端目标绝对路径：<ROOT>/user_{id}/<sanitized_name>"""
    ensure_root_dir()
    target_dir = user_upload_dir(user_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    return (target_dir / sanitize_filename(filename)).resolve()


def relative_to_root(path: str | Path) -> str:
    """
    将本地绝对路径转为相对 ROOT 的字符串形式。
    对于 S3 后端，约定 rel_path 统一为 'user_{id}/filename.ext'（由 file_storage 生成）。
    """
    p = Path(path).resolve()
    try:
        rel = p.relative_to(_ROOT)
        return str(rel).replace("\\", "/")
    except Exception:
        return p.name  # 降级：非 ROOT 子路径时返回 basename


def resolve_from_relative(rel_path: str) -> Path:
    """由相对路径还原本地绝对路径。"""
    if not rel_path:
        raise FileNotFoundError("empty relative path")
    p = (_ROOT / rel_path).resolve()
    return p


def build_file_url(rel_path: str) -> str:
    """
    构造公开访问 URL：
      - 若 settings.file_base_url 配置了前缀（CDN/反代），返回 <base>/<rel_path>
      - 否则返回 rel_path（由前端自行处理）
    """
    base = getattr(settings, "file_base_url", "") or ""
    if base:
        base = base.rstrip("/")
        return f"{base}/{rel_path.lstrip('/')}"
    return rel_path
