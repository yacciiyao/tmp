# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: AOA-01 选品机会扫描（关键词机会评分 + 市场概览）

from __future__ import annotations

from typing import Any, Dict, List, Optional

from domains.common_result_domain import (
    Article,
    Evidence,
    EvidenceSource,
    MysqlEvidenceRef,
    Recommendation,
    ResultSchemaV1,
    RagEvidenceRef,
)
from domains.amazon_domain import AmazonOpportunityScanReq


def _mysql_kw_evidence(row: Any, *, locator: Dict[str, Any]) -> Evidence:
    return Evidence(
        source=EvidenceSource.MYSQL,
        ref_mysql=MysqlEvidenceRef(
            table="src_amazon_keyword_metrics",
            pk={"id": int(row.id)},
            fields=["keyword", "search_volume", "cpc", "competition"],
            locator=dict(locator),
        ),
        excerpt=f"{row.keyword} sv={row.search_volume} cpc={row.cpc} comp={row.competition}",
    )


def _rag_evidence(hit: Dict[str, Any]) -> Evidence:
    return Evidence(
        source=EvidenceSource.RAG,
        ref_rag=RagEvidenceRef(
            kb_space=str(hit["kb_space"]),
            document_id=hit["document_id"],
            chunk_id=hit["chunk_id"],
            score=float(hit["score"]),
        ),
        excerpt=str(hit.get("content") or "")[:240],
    )


def analyze_aoa01(
    *,
    req: AmazonOpportunityScanReq,
    locator: Dict[str, Any],
    snapshots: List[Any],
    keyword_metrics: List[Any],
    rag_hits: Optional[List[Dict[str, Any]]],
) -> ResultSchemaV1:
    warnings: List[str] = []
    evidences: List[Evidence] = []
    recommendations: List[Recommendation] = []
    rankings: List[Dict[str, Any]] = []

    if not keyword_metrics:
        warnings.append("keyword_metrics is empty for this crawl_batch_no")
    else:
        # 机会分：sv*(1-comp) - 0.2*cpc（均为粗粒度展示；稳定可复现）
        rows = list(keyword_metrics)
        rows.sort(key=lambda r: (float(r.search_volume or 0.0), str(r.keyword)), reverse=True)

        top = rows[:80]
        scored: List[Dict[str, Any]] = []
        for r in top:
            sv = float(r.search_volume or 0.0)
            comp = float(r.competition or 0.0)
            cpc = float(r.cpc or 0.0)
            score = sv * (1.0 - comp) - 0.2 * cpc
            scored.append(
                {
                    "keyword": str(r.keyword),
                    "search_volume": sv,
                    "competition": comp,
                    "cpc": cpc,
                    "opportunity_score": float(score),
                    "_row": r,
                }
            )

        scored.sort(key=lambda x: (-x["opportunity_score"], x["keyword"]))
        rankings = [
            {
                "keyword": x["keyword"],
                "search_volume": x["search_volume"],
                "competition": x["competition"],
                "cpc": x["cpc"],
                "opportunity_score": x["opportunity_score"],
            }
            for x in scored[:30]
        ]

        # 取 Top3 输出建议（绑定证据）
        for x in scored[:3]:
            ev_idx = len(evidences)
            evidences.append(_mysql_kw_evidence(x["_row"], locator=locator))
            recommendations.append(
                Recommendation(
                    title=f"优先调研关键词「{x['keyword']}」对应的细分需求与差异化卖点",
                    category="opportunity",
                    priority="P0",
                    actions=[
                        "基于该关键词拉取 Top 50 竞品的价格带、评分与卖点摘要",
                        "提炼目标人群场景与痛点，形成 3 个可测试的产品方向",
                        "确认合规风险与材料/认证约束（如有）",
                    ],
                    expected_impact="提升选品命中率，缩短调研周期",
                    evidence_indexes=[ev_idx],
                )
            )

    # RAG 约束（可选）
    if rag_hits:
        for h in rag_hits[:3]:
            evidences.append(_rag_evidence(h))

    overview = {
        "site": str(req.site),
        "query": req.query.model_dump(mode="json"),
        "snapshot_count": len(snapshots),
        "keyword_metric_count": len(keyword_metrics),
        "top_n": int(req.filters.top_n),
    }

    insights = {
        "opportunity_method": "score = search_volume*(1-competition) - 0.2*cpc",
        "top_keywords": [r["keyword"] for r in rankings[:10]],
    }

    article_md = [
        f"# Amazon 选品机会扫描（{req.site.upper()}）",
        "",
        "## 输入",
        f"- 关键词：{req.query.keyword or '-'}",
        f"- 类目：{req.query.category or '-'}",
        f"- TopN：{req.filters.top_n}",
        "",
        "## 关键词机会 Top10",
    ]
    for i, r in enumerate(rankings[:10], start=1):
        article_md.append(
            f"{i}. **{r['keyword']}** 机会分={r['opportunity_score']:.2f} "
            f"(sv={r['search_volume']:.0f}, comp={r['competition']:.2f}, cpc={r['cpc']:.2f})"
        )

    return ResultSchemaV1(
        biz="amazon",
        task_kind=str(req.task_kind),
        input=req.model_dump(mode="json"),
        crawl=dict(locator),
        overview=overview,
        insights=insights,
        rankings=rankings,
        recommendations=recommendations,
        evidences=evidences,
        warnings=warnings,
        article=Article(
            title="Amazon 选品机会扫描",
            summary="基于关键词指标与批次快照进行机会排序与优先调研建议",
            markdown="\n".join(article_md),
        ),
    )
