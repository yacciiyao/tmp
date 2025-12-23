# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 众筹项目研究域模型（榜单 + 竞品对比 + 深度洞察）
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field

from domains.domain_base import DomainModel


class CrowdfundingTopReq(DomainModel):
    platform: str = Field(default="kickstarter", description="平台：kickstarter/indiegogo/makuake")
    time_range: str = Field(default="month", description="范围：month/quarter/year")
    category: Optional[str] = Field(default=None, description="类目过滤")
    top_n: int = Field(default=50, description="榜单数量")


class CrowdfundingProjectCompareReq(DomainModel):
    project_ids: List[str] = Field(default_factory=list, description="项目ID（平台原始ID或内部ID）")
    platform: Optional[str] = Field(default=None, description="平台（可选）")
    extra_notes: Optional[str] = Field(default=None, description="补充说明")


class CrowdfundingReportResult(DomainModel):
    summary: str = Field(..., description="核心结论摘要")
    rankings: List[Dict[str, Any]] = Field(default_factory=list, description="榜单")
    comparisons: List[Dict[str, Any]] = Field(default_factory=list, description="项目对比")
    insights: Dict[str, Any] = Field(default_factory=dict, description="趋势/定价/卖点/风险洞察")
    evidences: List[Dict[str, Any]] = Field(default_factory=list, description="可回溯证据")
