# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: AOA-04 Listing 审计与优化建议（确定性规则 + 关键词覆盖检查）

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from domains.common_result_domain import (
    Article,
    Evidence,
    EvidenceSource,
    MysqlEvidenceRef,
    Recommendation,
    ResultSchemaV1,
    RagEvidenceRef,
)
from domains.amazon_domain import AmazonListingAuditReq


_WORD_RE = re.compile(r"[a-zA-Z0-9]+")
_SPACE_RE = re.compile(r"\s+")


def _norm_text(s: str) -> str:
    s = (s or "").lower()
    s = _SPACE_RE.sub(" ", s).strip()
    return s


def _contains_kw(text: str, kw: str) -> bool:
    t = _norm_text(text)
    k = _norm_text(kw)
    if not k:
        return False
    return k in t


def _mysql_snapshot_evidence(row: Any, *, locator: Dict[str, Any]) -> Evidence:
    return Evidence(
        source=EvidenceSource.MYSQL,
        ref_mysql=MysqlEvidenceRef(
            table="src_amazon_product_snapshots",
            pk={"id": int(row.id)},
            fields=["asin", "title", "bullet_points", "description", "brand", "category", "price", "rating", "review_count"],
            locator=dict(locator),
        ),
        excerpt=f"{row.asin} title_len={len(str(row.title or ''))} bullets_len={len(str(row.bullet_points or ''))}",
    )


def _mysql_kw_evidence(row: Any, *, locator: Dict[str, Any]) -> Evidence:
    return Evidence(
        source=EvidenceSource.MYSQL,
        ref_mysql=MysqlEvidenceRef(
            table="src_amazon_keyword_metrics",
            pk={"id": int(row.id)},
            fields=["keyword", "search_volume", "competition", "cpc"],
            locator=dict(locator),
        ),
        excerpt=f"{row.keyword} sv={row.search_volume} comp={row.competition} cpc={row.cpc}",
    )


def _rag_evidence(hit: Dict[str, Any]) -> Evidence:
    return Evidence(
        source="rag",
        ref_rag=RagEvidenceRef(
            kb_space=str(hit["kb_space"]),
            document_id=hit["document_id"],
            chunk_id=hit["chunk_id"],
            score=float(hit["score"]),
        ),
        excerpt=str(hit.get("content") or "")[:240],
    )


def analyze_aoa04(
    *,
    req: AmazonListingAuditReq,
    locator: Dict[str, Any],
    snapshots: List[Any],
    keyword_metrics: List[Any],
    rag_hits: Optional[List[Dict[str, Any]]],
) -> ResultSchemaV1:
    warnings: List[str] = []
    evidences: List[Evidence] = []
    recommendations: List[Recommendation] = []

    asin = str(req.query.asin).strip()
    snap = None
    for s in snapshots:
        if str(getattr(s, "asin", "")) == asin:
            snap = s
            break

    if snap is None:
        warnings.append("target asin snapshot not found in this crawl_batch_no")
        # 仍返回结构化结果，便于定位问题
        return ResultSchemaV1(
            biz="amazon",
            task_kind=str(req.task_kind),
            input=req.model_dump(mode="json"),
            crawl=dict(locator),
            overview={"site": str(req.site), "asin": asin, "found_snapshot": False},
            insights={},
            recommendations=[],
            evidences=[],
            warnings=warnings,
            article=Article(title="Amazon Listing 审计与优化建议", summary="未找到目标ASIN快照", markdown="# 未找到目标ASIN快照\n"),
        )

    ev_snap_idx = len(evidences)
    evidences.append(_mysql_snapshot_evidence(snap, locator=locator))

    title = str(snap.title or "")
    bullets = str(snap.bullet_points or "")
    desc = str(snap.description or "")
    full_text = "\n".join([title, bullets, desc])

    # 规则：标题长度建议（经验区间，用于面试展示；不依赖 LLM）
    title_len = len(title)
    bullet_len = len(bullets)
    desc_len = len(desc)

    rule_findings: List[Dict[str, Any]] = []
    if title_len < 80:
        rule_findings.append({"rule": "title_length", "level": "high", "message": "标题过短，建议补充核心属性/场景/规格"})
    elif title_len > 200:
        rule_findings.append({"rule": "title_length", "level": "medium", "message": "标题偏长，建议压缩冗余词，保留核心关键词与卖点"})
    else:
        rule_findings.append({"rule": "title_length", "level": "ok", "message": "标题长度合理"})

    if bullet_len < 60:
        rule_findings.append({"rule": "bullet_points", "level": "high", "message": "五点描述信息不足，建议补齐功能/参数/场景/差异化"})
    else:
        rule_findings.append({"rule": "bullet_points", "level": "ok", "message": "五点描述长度满足基本信息密度"})

    if desc_len < 120:
        rule_findings.append({"rule": "description", "level": "medium", "message": "详情描述偏短，建议补充使用场景、材质、对比、FAQ"})
    else:
        rule_findings.append({"rule": "description", "level": "ok", "message": "详情描述长度满足基本信息密度"})

    # 关键词覆盖：取 search_volume Top 20，检查是否覆盖在 title/bullets/desc
    km = list(keyword_metrics)
    km.sort(key=lambda r: (float(r.search_volume or 0.0), str(r.keyword)), reverse=True)
    top_kws = km[:20]

    missing: List[str] = []
    used: List[str] = []
    kw_evidence_indexes: List[int] = []

    for r in top_kws:
        kw = str(r.keyword or "").strip()
        if not kw:
            continue
        if _contains_kw(full_text, kw):
            used.append(kw)
        else:
            missing.append(kw)
        # 为 top 20 关键词都附证据（方便复现/评测）
        kw_evidence_indexes.append(len(evidences))
        evidences.append(_mysql_kw_evidence(r, locator=locator))

    if missing:
        recommendations.append(
            Recommendation(
                title="补齐高搜索量关键词覆盖（标题/五点/描述分层布局）",
                category="listing",
                priority="P0",
                actions=[
                    f"优先补齐缺失关键词（示例）：{', '.join(missing[:8])}",
                    "标题放核心类目词 + 关键属性词；五点放场景/痛点/对比；描述放FAQ与细节",
                    "避免堆砌：同义词分散到 bullets/description，保持可读性",
                ],
                expected_impact="提升自然流量覆盖与转化一致性",
                evidence_indexes=[ev_snap_idx] + kw_evidence_indexes[:5],
            )
        )

    # 结构化输出 + 文章
    overview = {
        "site": str(req.site),
        "asin": asin,
        "found_snapshot": True,
        "title_len": title_len,
        "bullet_len": bullet_len,
        "description_len": desc_len,
        "rating": float(snap.rating or 0.0) if snap.rating is not None else None,
        "review_count": int(snap.review_count or 0) if snap.review_count is not None else None,
    }

    insights = {
        "rules": rule_findings,
        "keyword_coverage": {
            "used": used[:20],
            "missing": missing[:20],
            "checked_top_keywords": [str(r.keyword) for r in top_kws],
        },
    }

    if rag_hits:
        evidences.append(_rag_evidence(rag_hits[0]))

    md = [
        f"# Listing 审计与优化建议（{req.site.upper()}）",
        "",
        f"## ASIN：{asin}",
        "",
        "## 规则检查",
    ]
    for r in rule_findings:
        md.append(f"- [{r['level']}] {r['message']} (rule={r['rule']})")

    md.append("")
    md.append("## 关键词覆盖（Top20）")
    md.append(f"- 已覆盖：{', '.join(used[:12]) or '-'}")
    md.append(f"- 缺失：{', '.join(missing[:12]) or '-'}")

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
            title="Amazon Listing 审计与优化建议",
            summary="基于确定性规则与关键词覆盖检查生成可执行优化建议，并绑定证据链",
            markdown="\n".join(md),
        ),
    )
