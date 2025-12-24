# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: AOA-03 竞品矩阵与差异化（目标ASIN + 竞品对比）

from __future__ import annotations

from typing import Any, Dict, List, Optional

from domains.common_result_domain import Article, Evidence, EvidenceSource, MysqlEvidenceRef, Recommendation, ResultSchemaV1, RagEvidenceRef
from domains.amazon_domain import AmazonCompetitorMatrixReq


def _mysql_snapshot_evidence(row: Any, *, locator: Dict[str, Any]) -> Evidence:
    return Evidence(
        source=EvidenceSource.MYSQL,
        ref_mysql=MysqlEvidenceRef(
            table="src_amazon_product_snapshots",
            pk={"id": int(row.id)},
            fields=["asin", "title", "brand", "category", "price", "rating", "review_count", "bullet_points", "description"],
            locator=dict(locator),
        ),
        excerpt=f"{row.asin} price={row.price} rating={row.rating} rc={row.review_count}",
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


def analyze_aoa03(
    *,
    req: AmazonCompetitorMatrixReq,
    locator: Dict[str, Any],
    snapshots: List[Any],
    reviews: List[Any],
    rag_hits: Optional[List[Dict[str, Any]]],
) -> ResultSchemaV1:
    warnings: List[str] = []
    evidences: List[Evidence] = []
    recommendations: List[Recommendation] = []
    comparisons: List[Dict[str, Any]] = []

    target_asin = str(req.query.asin).strip()
    if not target_asin:
        warnings.append("asin is required but empty")

    by_asin: Dict[str, Any] = {str(s.asin): s for s in snapshots if getattr(s, "asin", None)}
    target = by_asin.get(target_asin)

    # 自动挑竞品：从同批次快照里按评论数/评分选 Top
    competitors: List[Any] = []
    if req.auto_pick_competitors:
        candidates = [s for s in snapshots if str(getattr(s, "asin", "")) and str(s.asin) != target_asin]
        candidates.sort(key=lambda x: (int(x.review_count or 0), float(x.rating or 0.0), str(x.asin)), reverse=True)
        competitors = candidates[:8]
    else:
        for a in req.query.competitor_asins:
            s = by_asin.get(str(a))
            if s:
                competitors.append(s)

    if not target:
        warnings.append("target asin snapshot not found in this crawl_batch_no")
    else:
        evidences.append(_mysql_snapshot_evidence(target, locator=locator))

    for c in competitors[:8]:
        evidences.append(_mysql_snapshot_evidence(c, locator=locator))

    def _row(s: Any) -> Dict[str, Any]:
        return {
            "asin": str(s.asin),
            "brand": str(s.brand or ""),
            "price": float(s.price or 0.0) if s.price is not None else None,
            "rating": float(s.rating or 0.0) if s.rating is not None else None,
            "review_count": int(s.review_count or 0) if s.review_count is not None else None,
            "title_len": len(str(s.title or "")),
        }

    if target:
        comparisons.append({"type": "target", "data": _row(target)})

    for c in competitors[:8]:
        comparisons.append({"type": "competitor", "data": _row(c)})

    if target and competitors:
        # 简单差异化建议：围绕“价格/评分/评论量”差距与内容长度
        best = max(competitors, key=lambda x: (float(x.rating or 0.0), int(x.review_count or 0), str(x.asin)))
        ev_idx = 0  # target evidence
        recommendations.append(
            Recommendation(
                title="对标高评分竞品，补齐卖点表达与差异化定位",
                category="competitor",
                priority="P0",
                actions=[
                    f"对标竞品 {best.asin} 的卖点结构，提炼其标题/五点的高频关键词与场景词",
                    "补齐目标款缺失的功能/场景信息（结合 VOC 反馈）",
                    "制定差异化卖点：材质/配件/保修/使用门槛等",
                ],
                expected_impact="提升 listing 转化与定位清晰度",
                evidence_indexes=[ev_idx],
            )
        )

    if rag_hits:
        evidences.append(_rag_evidence(rag_hits[0]))

    overview = {
        "site": str(req.site),
        "target_asin": target_asin,
        "competitor_count": len(competitors),
        "snapshot_count": len(snapshots),
        "review_sample_count": len(reviews),
    }

    insights = {
        "matrix_fields": ["price", "rating", "review_count", "title_len"],
        "notes": "竞品选择：同批次快照按评论数/评分排序（或使用指定 competitor_asins）",
    }

    md = [
        f"# Amazon 竞品矩阵与差异化（{req.site.upper()}）",
        "",
        f"## 目标 ASIN：{target_asin}",
        "",
        "## 对比矩阵（字段：price/rating/review_count/title_len）",
    ]
    for it in comparisons[:10]:
        d = it["data"]
        md.append(
            f"- [{it['type']}] {d['asin']} price={d['price']} rating={d['rating']} "
            f"rc={d['review_count']} title_len={d['title_len']}"
        )

    return ResultSchemaV1(
        biz="amazon",
        task_kind=str(req.task_kind),
        input=req.model_dump(mode="json"),
        crawl=dict(locator),
        overview=overview,
        insights=insights,
        comparisons=comparisons,
        recommendations=recommendations,
        evidences=evidences,
        warnings=warnings,
        article=Article(
            title="Amazon 竞品矩阵与差异化分析",
            summary="基于批次快照构建目标ASIN与竞品的核心指标矩阵，并给出差异化建议",
            markdown="\n".join(md),
        ),
    )
