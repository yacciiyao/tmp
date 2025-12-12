# -*- coding: utf-8 -*-
# @File: text_extraction_service.py
# @Author: yaccii
# @Description: 附件文本抽取（上传文件→解析→返回文本，不入库）

from __future__ import annotations
from typing import Tuple
from fastapi import UploadFile

from infrastructure.storage.file_storage import save_upload_file
from infrastructure.rag.loader import load_content
from infrastructure import mlogger


class TextExtractionService:
    """
    封装上传附件的文本抽取逻辑：
    - 保存文件；
    - 自动识别并抽取文本；
    - 供 ChatService 临时拼接上下文使用。
    """

    async def extract_from_upload(self, user_id: int, upload: UploadFile) -> Tuple[str, str, str]:
        rel_path, url = await save_upload_file(user_id, upload)
        try:
            content = await load_content(
                source_type="file",
                source_uri=rel_path,
                mime_type=upload.content_type,
                extra_meta={"filename": upload.filename},
            )
        except Exception as e:
            mlogger.exception(
                "TextExtractionService",
                "extract_from_upload",
                user_id=user_id,
                filename=upload.filename,
                error=str(e),
            )
            content = ""
        return rel_path, url, content or ""
