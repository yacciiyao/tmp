# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Amazon 运营助手请求协议（AOA-01~06 + 图片触发抓取）；输出统一 ResultSchemaV1

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field, model_validator

from domains.domain_base import DomainModel
from domains.common_result_domain import ResultSchemaV1


class AmazonSite(str):
    US = "us"
    UK = "uk"
    DE = "de"
    FR = "fr"
    IT = "it"
    ES = "es"
    JP = "jp"
    CA = "ca"


_ALLOWED_SITES = {
    AmazonSite.US,
    AmazonSite.UK,
    AmazonSite.DE,
    AmazonSite.FR,
    AmazonSite.IT,
    AmazonSite.ES,
    AmazonSite.JP,
    AmazonSite.CA,
}


class AmazonTaskKind(str):
    AOA_01 = "AOA-01"  # 选品机会扫描
    AOA_02 = "AOA-02"  # 市场调研简报
    AOA_03 = "AOA-03"  # 竞品矩阵与差异化
    AOA_04 = "AOA-04"  # Listing 审计与优化建议
    AOA_05 = "AOA-05"  # Review/VOC 洞察
    AOA_06 = "AOA-06"  # 产品优化与迭代建议


class AmazonTimeWindow(DomainModel):
    as_of: int = Field(..., description="分析基准日，YYYYMMDD（如 20251224）")
    lookback_days: int = Field(default=90, description="回看天数（1~365），默认90")

    @model_validator(mode="after")
    def _validate_window(self) -> "AmazonTimeWindow":
        if self.lookback_days <= 0 or self.lookback_days > 365:
            raise ValueError("lookback_days must be in [1, 365]")
        if self.as_of < 10000101 or self.as_of > 99991231:
            raise ValueError("as_of must be YYYYMMDD int")
        return self


class AmazonFilters(DomainModel):
    top_n: int = Field(default=50, description="TopN（1~200），默认50")
    price_min: Optional[float] = Field(default=None, description="最低价格（>=0）")
    price_max: Optional[float] = Field(default=None, description="最高价格（>=0）")

    @model_validator(mode="after")
    def _validate_filters(self) -> "AmazonFilters":
        if self.top_n <= 0 or self.top_n > 200:
            raise ValueError("top_n must be in [1, 200]")
        if self.price_min is not None and self.price_min < 0:
            raise ValueError("price_min must be >= 0")
        if self.price_max is not None and self.price_max < 0:
            raise ValueError("price_max must be >= 0")
        if self.price_min is not None and self.price_max is not None and self.price_max < self.price_min:
            raise ValueError("price_max must be >= price_min")
        return self


class AmazonQuery(DomainModel):
    keyword: Optional[str] = Field(default=None, description="关键词（用于抓取/筛选）")
    category: Optional[str] = Field(default=None, description="类目（用于抓取/筛选）")
    asin: Optional[str] = Field(default=None, description="目标ASIN（用于抓取/筛选）")
    competitor_asins: List[str] = Field(default_factory=list, description="竞品ASIN列表（可选）")


class AmazonOperationBaseReq(DomainModel):
    request_id: Optional[str] = Field(default=None, description="请求唯一标识（用于串联日志/trace）")
    site: str = Field(default=AmazonSite.US, description="站点")
    time_window: AmazonTimeWindow = Field(..., description="时间窗口")
    filters: AmazonFilters = Field(default_factory=AmazonFilters, description="过滤条件")

    use_rag: bool = Field(default=False, description="是否启用RAG（内部资料检索）")
    kb_space: Optional[str] = Field(default=None, description="RAG space（use_rag=true 时必填）")
    extra_notes: Optional[str] = Field(default=None, description="运营补充说明（目标人群/约束/策略偏好等）")

    @model_validator(mode="after")
    def _validate_rag(self) -> "AmazonOperationBaseReq":
        if self.site not in _ALLOWED_SITES:
            raise ValueError(f"site must be one of {sorted(list(_ALLOWED_SITES))}")
        if self.use_rag and not self.kb_space:
            raise ValueError("kb_space is required when use_rag=true")
        if (not self.use_rag) and (self.kb_space is not None):
            raise ValueError("kb_space must be None when use_rag=false")
        return self


class AmazonOpportunityScanReq(AmazonOperationBaseReq):
    task_kind: str = Field(default=AmazonTaskKind.AOA_01, description="任务类型")
    query: AmazonQuery = Field(..., description="查询条件")

    @model_validator(mode="after")
    def _validate_req(self) -> "AmazonOpportunityScanReq":
        if not (self.query.keyword or self.query.category):
            raise ValueError("keyword or category is required")
        if self.query.asin is not None:
            raise ValueError("asin must be None for opportunity scan")
        return self


class AmazonMarketResearchReq(AmazonOperationBaseReq):
    task_kind: str = Field(default=AmazonTaskKind.AOA_02, description="任务类型")
    query: AmazonQuery = Field(..., description="查询条件")

    @model_validator(mode="after")
    def _validate_req(self) -> "AmazonMarketResearchReq":
        if not (self.query.keyword or self.query.category):
            raise ValueError("keyword or category is required")
        return self


class AmazonCompetitorMatrixReq(AmazonOperationBaseReq):
    task_kind: str = Field(default=AmazonTaskKind.AOA_03, description="任务类型")
    query: AmazonQuery = Field(..., description="查询条件")
    auto_pick_competitors: bool = Field(default=True, description="是否自动挑选竞品")

    @model_validator(mode="after")
    def _validate_req(self) -> "AmazonCompetitorMatrixReq":
        if not self.query.asin:
            raise ValueError("asin is required")
        if (not self.auto_pick_competitors) and (not self.query.competitor_asins):
            raise ValueError("competitor_asins is required when auto_pick_competitors=false")
        return self


class AmazonListingAuditReq(AmazonOperationBaseReq):
    task_kind: str = Field(default=AmazonTaskKind.AOA_04, description="任务类型")
    query: AmazonQuery = Field(..., description="查询条件")
    brand_tone: Optional[str] = Field(default=None, description="品牌语气（可选）")

    @model_validator(mode="after")
    def _validate_req(self) -> "AmazonListingAuditReq":
        if not self.query.asin:
            raise ValueError("asin is required")
        return self


class AmazonReviewVocReq(AmazonOperationBaseReq):
    task_kind: str = Field(default=AmazonTaskKind.AOA_05, description="任务类型")
    query: AmazonQuery = Field(..., description="查询条件")

    @model_validator(mode="after")
    def _validate_req(self) -> "AmazonReviewVocReq":
        if self.query.asin:
            return self
        if not (self.query.keyword or self.query.category):
            raise ValueError("asin or (keyword/category) is required")
        return self


class AmazonProductImprovementReq(AmazonOperationBaseReq):
    task_kind: str = Field(default=AmazonTaskKind.AOA_06, description="任务类型")
    query: AmazonQuery = Field(..., description="查询条件")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="约束条件（成本/材质/认证/包装/交期等）")

    @model_validator(mode="after")
    def _validate_req(self) -> "AmazonProductImprovementReq":
        if not self.query.asin:
            raise ValueError("asin is required")
        return self


class AmazonImageToSpiderReq(DomainModel):
    request_id: Optional[str] = Field(default=None, description="请求唯一标识（用于串联日志/trace）")
    site: str = Field(default=AmazonSite.US, description="站点")
    task_kind: str = Field(..., description="任务类型，仅允许 AOA-01/02/03")
    storage_uri: str = Field(..., description="图片本地存储URI（由上传接口返回）")
    hint_keyword: Optional[str] = Field(default=None, description="提示关键词（可选）")
    hint_category: Optional[str] = Field(default=None, description="提示类目（可选）")
    top_n: int = Field(default=50, description="TopN（1~200）")

    @model_validator(mode="after")
    def _validate_req(self) -> "AmazonImageToSpiderReq":
        if self.site not in _ALLOWED_SITES:
            raise ValueError(f"site must be one of {sorted(list(_ALLOWED_SITES))}")
        if self.task_kind not in (AmazonTaskKind.AOA_01, AmazonTaskKind.AOA_02, AmazonTaskKind.AOA_03):
            raise ValueError("task_kind must be one of AOA-01/AOA-02/AOA-03")
        if self.top_n <= 0 or self.top_n > 200:
            raise ValueError("top_n must be in [1, 200]")
        if not self.storage_uri:
            raise ValueError("storage_uri is required")
        return self


AmazonResultV1 = ResultSchemaV1
