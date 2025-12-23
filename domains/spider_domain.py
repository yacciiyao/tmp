# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 爬虫任务域模型（只负责触发/等待就绪/读取MySQL）

from __future__ import annotations

from enum import IntEnum
from typing import Any, Dict, List, Optional

from pydantic import Field

from domains.domain_base import DomainModel, now_ts


class SpiderTaskStatus(IntEnum):
    CREATED = 10  # 已创建（待入队）
    ENQUEUED = 20  # 已入队（等待爬虫处理）
    READY = 30  # 结果已就绪（MySQL已写入）
    FAILED = 40  # 失败


class SpiderTaskCreateReq(DomainModel):
    task_type: str = Field(..., description="任务类型，如 amazon.collect")
    task_key: str = Field(..., description="任务唯一Key（幂等）")
    biz: str = Field(..., description="业务域，如 amazon/brand/crowdfunding")
    payload: Dict[str, Any] = Field(default_factory=dict, description="发送给爬虫的结构化参数")
    result_tables: List[str] = Field(default_factory=list, description="期望写入的MySQL表名列表")


class SpiderTaskVO(DomainModel):
    task_id: int = Field(..., description="任务ID")
    task_type: str = Field(..., description="任务类型")
    task_key: str = Field(..., description="任务唯一Key")
    biz: str = Field(..., description="业务域")
    status: int = Field(..., description="任务状态（SpiderTaskStatus）")

    payload: Dict[str, Any] = Field(default_factory=dict, description="爬虫参数")
    result_tables: List[str] = Field(default_factory=list, description="结果表")
    result_locator: Optional[Dict[str, Any]] = Field(default=None, description="结果定位信息（如 crawl_batch_no）")

    error_code: Optional[str] = Field(default=None, description="错误码")
    error_message: Optional[str] = Field(default=None, description="错误信息")

    created_at: int = Field(default_factory=now_ts, description="创建时间(秒)")
    updated_at: int = Field(default_factory=now_ts, description="更新时间(秒)")

    created_by: Optional[int] = Field(default=None, description="创建人用户ID")
