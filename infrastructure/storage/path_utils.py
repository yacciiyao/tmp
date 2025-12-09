# -*- coding: utf-8 -*-
# @File: path_utils.py
# @Author: yaccii
# @Description:
from __future__ import annotations

import os
import re
from pathlib import Path

from infrastructure.config import settings


_root = Path(settings.file_storage_root).resolve()


def ensure_root_dir() -> Path:
    _root.mkdir(parents=True, exist_ok=True)
    return _root


def sanitize_filename(filename: str) -> str:
    name = os.path.basename(filename)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name or "file"


def user_upload_dir(user_id: int) -> Path:
    root = ensure_root_dir()
    d = root / f"user_{user_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def build_user_file_path(user_id: int, filename: str) -> Path:
    safe_name = sanitize_filename(filename)
    return user_upload_dir(user_id) / safe_name


def relative_to_root(path: Path) -> str:
    return str(path.resolve().relative_to(_root))


def resolve_from_relative(rel_path: str) -> Path:
    return _root / rel_path


def build_file_url(rel_path: str) -> str:
    base = settings.file_base_url
    if not base:
        return rel_path
    return f"{base.rstrip('/')}/{rel_path.lstrip('/')}"
