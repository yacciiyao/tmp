# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: AOA-02 市场调研简报（价格带/品牌集中度/评分与评论量概览）

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from domains.common_result_domain import Article, Evidence, EvidenceSource, MysqlEvidenceRef, Recommendation, ResultSchemaV1, RagEvidenceRef
from domains.amazon_domain import AmazonMarketResearchReq


def _bucket_price(p: float) -> str:
    if p < 10:
        return "<10"
    if p < 20:
        return "10-20"
    if p < 30:
        return "20-30"
    if p < 50:
        return "30-50"
    if p < 80:
        return "50-80"
    if p < 120:
        return "80-120"
    return ">=120"


def _mysql_snapshot_evidence(row: Any, *, locator: Dict[str, Any]) -> Evidence:
    return Evidence(
        source=EvidenceSource.MYSQL,
        ref_mysql=MysqlEvidenceRef(
            table="src_amazon_product_snapshots",
            pk={"id": int(row.id)},
            fields=["asin", "title", "brand", "category", "price", "rating", "review_count"],
            locator=dict(locator),
        ),
        excerpt=f"{row.asin} {row.brand or '-'} price={row.price} rating={row.rating} rc={row.review_count}",
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


def analyze_aoa02(
    *,
    req: AmazonMarketResearchReq,
    locator: Dict[str, Any],
    snapshots: List[Any],
    keyword_metrics: List[Any],
    rag_hits: Optional[List[Dict[str, Any]]],
) -> ResultSchemaV1:
    warnings: List[str] = []
    evidences: List[Evidence] = []
    recommendations: List[Recommendation] = []

    if not snapshots:
        warnings.append("snapshots is empty for this crawl_batch_no")

    prices: List[float] = []
    ratings: List[float] = []
    rc_list: List[int] = []
    brand_counter: Counter[str] = Counter()
    price_bucket: Counter[str] = Counter()

    for s in snapshots:
        if s.brand:
            brand_counter[str(s.brand)] += 1
        if s.price is not None:
            p = float(s.price)
            prices.append(p)
            price_bucket[_bucket_price(p)] += 1
        if s.rating is not None:
            ratings.append(float(s.rating))
        if s.review_count is not None:
            rc_list.append(int(s.review_count))

    def _mean(vals: List[float]) -> float:
        if not vals:
            return 0.0
        return sum(vals) / float(len(vals))

    top_brands = brand_counter.most_common(10)
    pb = sorted(price_bucket.items(), key=lambda x: x[0])

    # 证据：取 3 个代表性样本（按评论数降序）
    s_sorted = sorted(
        snapshots,
        key=lambda x: (int(x.review_count or 0), str(x.asin)),
        reverse=True,
    )
    for s in s_sorted[:3]:
        evidences.append(_mysql_snapshot_evidence(s, locator=locator))

    if top_brands:
        ev_idx = 0 if evidences else -1
        recommendations.append(
            Recommendation(
                title="优先研究 Top 品牌的核心卖点与定价策略，提炼差异化切入点",
                category="market",
                priority="P0",
                actions=[
                    "拆解 Top3 品牌的标题/五点/主图策略（如有数据）",
                    "对比价格带与评分/评论量，找出可突围的细分档位",
                ],
                expected_impact="缩短市场调研时间，提升差异化定位质量",
                evidence_indexes=[ev_idx] if ev_idx >= 0 else [],
            )
        )

    if rag_hits:
        evidences.append(_rag_evidence(rag_hits[0]))

    overview = {
        "site": str(req.site),
        "query": req.query.model_dump(mode="json"),
        "snapshot_count": len(snapshots),
        "avg_price": round(_mean(prices), 2),
        "avg_rating": round(_mean(ratings), 2),
        "avg_review_count": round(_mean([float(x) for x in rc_list]), 2) if rc_list else 0.0,
    }

    insights = {
        "price_buckets": [{"bucket": k, "count": v} for k, v in pb],
        "top_brands": [{"brand": b, "count": c} for b, c in top_brands],
        "keyword_metric_count": len(keyword_metrics),
    }

    md = [
        f"# Amazon 市场调研简报（{req.site.upper()}）",
        "",
        "## 概览",
        f"- 样本量（快照）：{len(snapshots)}",
        f"- 平均价格：{overview['avg_price']}",
        f"- 平均评分：{overview['avg_rating']}",
        f"- 平均评论数：{overview['avg_review_count']}",
        "",
        "## 价格带分布",
    ]
    for it in insights["price_buckets"]:
        md.append(f"- {it['bucket']}: {it['count']}")

    md.append("")
    md.append("## 品牌集中度 Top10")
    for it in insights["top_brands"]:
        md.append(f"- {it['brand']}: {it['count']}")

    return ResultSchemaV1(
        biz="amazon",
        task_kind=str(req.task_kind),
        input=req.model_dump(mode="json"),
        crawl=dict(locator),
        overview=overview,
        insights=insights,
        recommendations=recommendations,
        evidences=evidences,
        warnings=warnings,
        article=Article(
            title="Amazon 市场调研简报",
            summary="基于批次快照生成价格带、品牌集中度与评分/评论量概览",
            markdown="\n".join(md),
        ),
    )
