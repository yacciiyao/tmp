# -*- coding: utf-8 -*-
# @File: dto.py
# @Author: yaccii
# @Time: 2025-12-10 09:27
# @Description:

from pydantic import BaseModel, Field


class FileUploadResponse(BaseModel):
    """
    通用文件上传返回 DTO。

    - rel_path: 相对 file_storage_root 的路径，便于服务端内部引用或入库。
    - url: 文件对外可访问 URL（如配置了 file_base_url），供前端预览/下载。
    - absolute_path: 服务器本地绝对路径，可直接作为 RAG 文档 source_uri 使用。
    """

    rel_path: str = Field(
        ...,
        description="相对文件根目录的存储路径，例如 'user_1/2025/01/xxx.pdf'",
    )
    url: str = Field(
        ...,
        description="文件访问 URL，如果配置了 file_base_url 则为完整 URL，否则为相对路径",
    )
    absolute_path: str = Field(
        ...,
        description="服务器本地绝对路径，可作为 RAG 文档 source_uri",
    )
    file_name: str = Field(
        ...,
        description="上传时的原始文件名",
    )
    mime_type: str = Field(
        ...,
        description="文件 MIME 类型，例如 'application/pdf'",
    )
    size_bytes: int = Field(
        ...,
        description="文件大小（字节）",
    )
