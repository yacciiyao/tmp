# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 出海品牌研究域模型（基于爬虫结构化数据 + RAG公开信息）

from __future__ import annotations

from typing import Optional, List, Dict, Any

from pydantic import Field

from domains.domain_base import DomainModel


class BrandHotspotReq(DomainModel):
    brand_id: Optional[int] = Field(default=None, description="品牌ID")
    brand_name: Optional[str] = Field(default=None, description="品牌名（可选）")
    dimension: str = Field(default="month", description="维度：month/quarter/year")
    top_n: int = Field(default=20, description="榜单数量")


class BrandCompareReq(DomainModel):
    brand_ids: List[int] = Field(default_factory=list, description="对比品牌ID列表")
    dimension: str = Field(default="month", description="维度：month/quarter/year")
    extra_notes: Optional[str] = Field(default=None, description="补充说明（业务侧输入）")


class BrandReportResult(DomainModel):
    summary: str = Field(..., description="核心结论摘要")
    rankings: List[Dict[str, Any]] = Field(default_factory=list, description="榜单/热度汇总")
    insights: Dict[str, Any] = Field(default_factory=dict, description="洞察（趋势/渠道/区域/品类）")
    comparisons: List[Dict[str, Any]] = Field(default_factory=list, description="品牌对比")
    evidences: List[Dict[str, Any]] = Field(default_factory=list, description="可回溯证据")
