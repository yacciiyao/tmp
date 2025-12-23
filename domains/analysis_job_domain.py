# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 分析任务数据结构（用于接口与服务层）

from __future__ import annotations

from enum import IntEnum
from typing import Dict, Any, Optional

from pydantic import Field

from domains.domain_base import DomainModel


class AnalysisJobType(IntEnum):
    AMAZON_MARKET_REPORT = 1
    BRAND_REPORT = 2
    CROWDFUNDING_REPORT = 3


class AnalysisJobStatus(IntEnum):
    PENDING = 10
    READY = 15
    RUNNING = 20
    SUCCEEDED = 30
    FAILED = 40


class AnalysisJobCreate(DomainModel):
    job_type: int = Field(..., description="任务类型（AnalysisJobType）")
    payload: Dict[str, Any] = Field(default_factory=dict, description="任务输入（结构化）")
    spider_task_id: Optional[int] = Field(default=None, description="关联爬虫任务ID（可选）")
    trace: Dict[str, Any] = Field(default_factory=dict, description="可回溯信息（来源/筛选条件/版本等）")


class AnalysisJobVO(DomainModel):
    job_id: int = Field(..., description="任务ID")
    job_type: int = Field(..., description="任务类型（AnalysisJobType）")
    status: int = Field(..., description="任务状态（AnalysisJobStatus）")

    created_by: int = Field(..., description="创建人用户ID")
    spider_task_id: Optional[int] = Field(default=None, description="关联爬虫任务ID（可选）")

    payload: Dict[str, Any] = Field(default_factory=dict, description="任务输入（结构化）")
    trace: Dict[str, Any] = Field(default_factory=dict, description="可回溯信息")
    result: Dict[str, Any] = Field(default_factory=dict, description="任务输出（结构化）")

    error_code: str = Field(default="", description="错误码")
    error_message: str = Field(default="", description="错误信息")

    created_at: int = Field(default=0, description="创建时间戳（秒）")
    updated_at: int = Field(default=0, description="更新时间戳（秒）")
