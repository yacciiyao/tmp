# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 亚马逊运营域模型（面向“帮助决策”，可回溯）
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field

from domains.domain_base import DomainModel


class AmazonSite(str):
    US = "us"
    UK = "uk"
    DE = "de"
    FR = "fr"
    IT = "it"
    ES = "es"
    JP = "jp"
    CA = "ca"


class AmazonMarketReportReq(DomainModel):
    """输入可以是关键词/ASIN/类目，最终都落到“一个可分析的候选集合”"""

    site: str = Field(default="us", description="站点")
    keyword: Optional[str] = Field(default=None, description="关键词")
    asin: Optional[str] = Field(default=None, description="ASIN")
    category: Optional[str] = Field(default=None, description="类目（可选）")
    top_n: int = Field(default=10, description="候选竞品数量")


class AmazonEvidence(DomainModel):
    """证据：来自结构化表、评论、以及可选的RAG文档引用"""

    source: str = Field(..., description="数据来源：mysql/reviews/rag/web等")
    ref: Dict[str, Any] = Field(default_factory=dict, description="引用定位（asin/review_id/chunk_id等）")
    excerpt: Optional[str] = Field(default=None, description="摘要片段")


class AmazonMarketReportResult(DomainModel):
    """结构化输出，便于前端展示与回溯"""

    summary: str = Field(..., description="核心结论摘要")
    market: Dict[str, Any] = Field(default_factory=dict, description="市场分析")
    competitors: List[Dict[str, Any]] = Field(default_factory=list, description="竞品拆解")
    voc: Dict[str, Any] = Field(default_factory=dict, description="评论VOC洞察")
    listing_suggestions: Dict[str, Any] = Field(default_factory=dict, description="Listing诊断与改写建议")
    risks: List[Dict[str, Any]] = Field(default_factory=list, description="风险提示")
    evidences: List[AmazonEvidence] = Field(default_factory=list, description="证据列表（可回溯）")
