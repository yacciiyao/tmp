# -*- coding: utf-8 -*-
# @File: file_service.py
# @Author: yaccii
# @Time: 2025-12-10 09:27
# @Description:

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import UploadFile

from application.file.dto import FileUploadResponse
from infrastructure.mlogger import info, exception
from infrastructure.rag.loader import load_content
from infrastructure.storage.file_storage import save_upload_file
from infrastructure.storage.path_utils import resolve_from_relative


class FileService:
    """
    文件相关应用服务。

    当前负责：
    - 接收用户 / 系统 上传的 UploadFile
    - 调用 infrastructure.storage 落盘
    - 补全文件元信息，返回给上层（router / 其它 service）
    - 可选：调用 loader 抽取文本内容（多模态解析）

    注意：
    - 不负责 RAG 业务（不创建 rag_document / 不写向量库）
    - 不负责 Chat 业务（不创建 ChatMessage / ChatAttachment）
    """

    def __init__(self) -> None:
        # 目前没有状态；预留位置，后续如需注入 DB / 配置可在此调整
        ...

    # ------------------------------------------------------------------
    # 通用：按 user_id 保存文件（原有接口，保持不变）
    # ------------------------------------------------------------------
    async def upload_user_file(
        self,
        *,
        user_id: int,
        upload: UploadFile,
    ) -> FileUploadResponse:
        """
        保存用户上传文件，并返回文件元信息。

        - 使用 save_upload_file(user_id, upload) 落地到本地磁盘；
        - 通过 resolve_from_relative(rel_path) 计算绝对路径；
        - 补充文件大小、文件名、MIME 类型等信息。
        """
        try:
            rel_path, url = await save_upload_file(user_id=user_id, upload=upload)

            # 计算绝对路径
            full_path: Path = resolve_from_relative(rel_path)

            # 尝试获取文件大小
            try:
                size_bytes = full_path.stat().st_size
            except OSError:
                size_bytes = 0

            file_name: str = upload.filename or ""
            mime_type: str = upload.content_type or "application/octet-stream"

            resp = FileUploadResponse(
                rel_path=rel_path,
                url=url,
                absolute_path=str(full_path),
                file_name=file_name,
                mime_type=mime_type,
                size_bytes=size_bytes,
            )

            info(
                "FileService",
                "upload_user_file",
                user_id=user_id,
                rel_path=rel_path,
                size_bytes=size_bytes,
            )

            return resp

        except Exception:
            exception(
                "FileService",
                "upload_user_file",
                user_id=user_id,
                filename=getattr(upload, "filename", None),
            )
            # 交由 FastAPI 统一异常处理
            raise

    # ------------------------------------------------------------------
    # 管理员 RAG 导入：统一入口
    # ------------------------------------------------------------------
    async def upload_rag_file(
        self,
        *,
        corpus_id: int,
        uploader_id: int,
        upload: UploadFile,
    ) -> FileUploadResponse:
        """
        管理员导入 RAG 语料使用的文件保存。

        设计约定：
        - 底层仍复用 upload_user_file，但固定使用 user_id=0 作为“系统用户”目录，
          以便逻辑上隔离普通用户上传（user_{real_user_id}）。
        - corpus_id / uploader_id 仅体现在日志与后续 rag_document.extra_meta 中，
          不写入 FileUploadResponse 结构体（保持对现有调用方的兼容性）。
        """
        resp = await self.upload_user_file(user_id=0, upload=upload)

        info(
            "FileService",
            "upload_rag_file",
            corpus_id=corpus_id,
            uploader_id=uploader_id,
            rel_path=resp.rel_path,
            size_bytes=resp.size_bytes,
        )

        return resp

    # ------------------------------------------------------------------
    # 多模态解析：文件 → 文本（RAG / Chat 可共用）
    # ------------------------------------------------------------------
    async def parse_file_to_text(
        self,
        *,
        absolute_path: str,
        mime_type: str,
        source_type: str = "file",
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        使用现有 loader 能力，从本地文件抽取文本内容。

        当前支持（由 loader 决定）：
        - source_type = "file": txt / pdf 按 mime_type 走对应分支；
        - source_type = "url": 从远程 URL 拉取文本；
        - source_type = "text": 直接使用 extra_meta["text"] 或 source_uri。

        后续可以在 loader 里扩展 image/audio/video 等 mime_type 的处理：
        - image/*  → OCR → 文本
        - audio/*  → ASR → 文本
        - video/*  → 提取音轨 + ASR → 文本
        """
        extra: Dict[str, Any] = dict(extra_meta or {})

        info(
            "FileService",
            "parse_file_to_text:start",
            source_type=source_type,
            path=absolute_path,
            mime_type=mime_type,
        )

        try:
            text: str = await load_content(
                source_type=source_type,
                source_uri=absolute_path,
                mime_type=mime_type,
                extra_meta=extra,
            )
        except Exception:
            exception(
                "FileService",
                "parse_file_to_text",
                source_type=source_type,
                path=absolute_path,
                mime_type=mime_type,
            )
            raise

        info(
            "FileService",
            "parse_file_to_text:done",
            source_type=source_type,
            path=absolute_path,
            mime_type=mime_type,
            length=len(text),
        )

        return text
