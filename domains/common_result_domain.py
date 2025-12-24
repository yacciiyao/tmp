# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 统一结果协议 ResultSchema v1（跨 Amazon/品牌/众筹复用；含证据链与可观测trace）

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field, model_validator

from domains.domain_base import DomainModel, now_ts


class EvidenceSource(str):
    MYSQL = "mysql"
    RAG = "rag"


class MysqlEvidenceRef(DomainModel):
    table: str = Field(..., description="表名（如 src_amazon_reviews）")
    pk: Dict[str, Any] = Field(..., description="主键/唯一键组合（必须非空 dict）")
    fields: List[str] = Field(..., description="引用字段列表（必须非空）")
    locator: Dict[str, Any] = Field(..., description="定位信息（至少包含 crawl_batch_no/site）")

    @model_validator(mode="after")
    def _validate_ref(self) -> "MysqlEvidenceRef":
        if not self.table:
            raise ValueError("table is required")
        if not isinstance(self.pk, dict) or not self.pk:
            raise ValueError("pk must be a non-empty dict")
        if not isinstance(self.fields, list) or not self.fields:
            raise ValueError("fields must be a non-empty list")
        if not isinstance(self.locator, dict) or not self.locator:
            raise ValueError("locator must be a non-empty dict")
        return self


class RagEvidenceRef(DomainModel):
    kb_space: str = Field(..., description="知识库空间")
    document_id: Any = Field(..., description="文档ID（int/str）")
    chunk_id: Any = Field(..., description="chunk ID（int/str）")
    score: float = Field(..., description="检索得分")

    @model_validator(mode="after")
    def _validate_ref(self) -> "RagEvidenceRef":
        if not self.kb_space:
            raise ValueError("kb_space is required")
        return self


class Evidence(DomainModel):
    source: str = Field(..., description="来源：mysql/rag")
    ref_mysql: Optional[MysqlEvidenceRef] = Field(default=None, description="mysql证据引用")
    ref_rag: Optional[RagEvidenceRef] = Field(default=None, description="rag证据引用")
    excerpt: Optional[str] = Field(default=None, description="证据摘要片段（可选）")
    note: Optional[str] = Field(default=None, description="补充说明（可选）")

    @model_validator(mode="after")
    def _validate_evidence(self) -> "Evidence":
        if self.source == EvidenceSource.MYSQL:
            if self.ref_mysql is None:
                raise ValueError("ref_mysql is required when source=mysql")
            if self.ref_rag is not None:
                raise ValueError("ref_rag must be None when source=mysql")
        elif self.source == EvidenceSource.RAG:
            if self.ref_rag is None:
                raise ValueError("ref_rag is required when source=rag")
            if self.ref_mysql is not None:
                raise ValueError("ref_mysql must be None when source=rag")
        else:
            raise ValueError("source must be mysql or rag")
        return self


class Recommendation(DomainModel):
    title: str = Field(..., description="建议标题（一句话）")
    category: str = Field(..., description="建议分类（业务自定义，但同业务内必须统一命名）")
    priority: str = Field(..., description="优先级（如 P0/P1/P2 或 high/medium/low）")
    actions: List[str] = Field(default_factory=list, description="可执行动作清单")
    expected_impact: Optional[str] = Field(default=None, description="预期影响（可选）")
    evidence_indexes: List[int] = Field(default_factory=list, description="绑定 evidences 的下标（必须可回溯）")

    @model_validator(mode="after")
    def _validate_indexes(self) -> "Recommendation":
        for idx in self.evidence_indexes:
            if idx < 0:
                raise ValueError("evidence_indexes must be >= 0")
        return self


class Article(DomainModel):
    title: str = Field(default="", description="文章标题")
    summary: str = Field(default="", description="文章摘要")
    markdown: str = Field(default="", description="markdown正文")


class StepTrace(DomainModel):
    step: str = Field(..., description="步骤名（如 load_data/analyze/build_evidence/compose/persist）")
    started_at: int = Field(..., description="开始时间戳（秒）")
    finished_at: int = Field(..., description="结束时间戳（秒）")
    duration_ms: int = Field(..., description="耗时（毫秒）")
    note: Optional[str] = Field(default=None, description="补充说明（可选）")


class ModelTrace(DomainModel):
    model_name: Optional[str] = Field(default=None, description="模型名称（可选）")
    prompt_version: Optional[str] = Field(default=None, description="prompt版本（可选）")
    input_tokens: Optional[int] = Field(default=None, description="输入token（可选）")
    output_tokens: Optional[int] = Field(default=None, description="输出token（可选）")
    cost_usd: Optional[float] = Field(default=None, description="成本估算（可选）")
    rag_hits: Optional[int] = Field(default=None, description="RAG命中条数（可选）")
    note: Optional[str] = Field(default=None, description="补充说明（可选）")


class Trace(DomainModel):
    request_id: Optional[str] = Field(default=None, description="请求ID（用于串联）")

    job_id: Optional[int] = Field(default=None, description="分析任务ID")
    job_type: Optional[int] = Field(default=None, description="分析任务类型")
    status: Optional[int] = Field(default=None, description="分析任务状态")
    payload: Optional[Dict[str, Any]] = Field(default=None, description="job payload（可选回显，建议脱敏）")
    error_code: Optional[str] = Field(default=None, description="job错误码（可选）")
    error_message: Optional[str] = Field(default=None, description="job错误信息（可选）")
    created_at: Optional[int] = Field(default=None, description="job创建时间戳（秒）")
    updated_at: Optional[int] = Field(default=None, description="job更新时间戳（秒）")
    created_by: Optional[int] = Field(default=None, description="job创建人用户ID")

    spider_task_id: Optional[int] = Field(default=None, description="爬虫任务ID")
    spider_status: Optional[int] = Field(default=None, description="爬虫任务状态")
    spider_error_code: Optional[str] = Field(default=None, description="爬虫错误码（可选）")
    spider_error_message: Optional[str] = Field(default=None, description="爬虫错误信息（可选）")

    crawl_locator: Optional[Dict[str, Any]] = Field(default=None, description="定位信息（如 crawl_batch_no/site）")
    task_kind: Optional[str] = Field(default=None, description="业务任务类型")
    biz: Optional[str] = Field(default=None, description="业务标识")

    steps: List[StepTrace] = Field(default_factory=list, description="节点级trace（可选）")
    model: ModelTrace = Field(default_factory=ModelTrace, description="模型/检索trace（可选）")


class Meta(DomainModel):
    schema_version: str = Field(default="v1", description="schema版本")
    ruleset_version: str = Field(default="v1", description="规则/策略版本")
    generated_at: int = Field(default_factory=now_ts, description="结果生成时间戳（秒）")
    operator_user_id: Optional[int] = Field(default=None, description="操作者用户ID（可选）")


class ResultSchemaV1(DomainModel):
    biz: str = Field(..., description="业务标识（amazon/brand/crowdfunding）")
    task_kind: str = Field(..., description="任务类型（业务内枚举）")

    input: Dict[str, Any] = Field(default_factory=dict, description="输入回显（规范化后的req）")
    crawl: Dict[str, Any] = Field(default_factory=dict, description="爬虫定位信息（locator展开/补充）")

    overview: Dict[str, Any] = Field(default_factory=dict, description="概览")
    insights: Dict[str, Any] = Field(default_factory=dict, description="洞察")
    rankings: List[Dict[str, Any]] = Field(default_factory=list, description="榜单")
    comparisons: List[Dict[str, Any]] = Field(default_factory=list, description="对比矩阵")

    recommendations: List[Recommendation] = Field(default_factory=list, description="建议清单")
    evidences: List[Evidence] = Field(default_factory=list, description="证据链")

    warnings: List[str] = Field(default_factory=list, description="非致命告警")
    article: Article = Field(default_factory=Article, description="报道/简报文章")

    meta: Meta = Field(default_factory=Meta, description="元信息")
    trace: Trace = Field(default_factory=Trace, description="执行链路追踪")

    result_created_at: Optional[int] = Field(default=None, description="结果首次落库时间戳（秒）")
    result_updated_at: Optional[int] = Field(default=None, description="结果更新时间戳（秒）")

    @model_validator(mode="after")
    def _validate_binding(self) -> "ResultSchemaV1":
        # recommendations.evidence_indexes 必须可回溯到 evidences
        if not self.evidences:
            for rec in self.recommendations:
                if rec.evidence_indexes:
                    raise ValueError("recommendations.evidence_indexes out of range")
            return self

        max_idx = len(self.evidences) - 1
        for rec in self.recommendations:
            for idx in rec.evidence_indexes:
                if idx > max_idx:
                    raise ValueError("recommendations.evidence_indexes out of range")
        return self
