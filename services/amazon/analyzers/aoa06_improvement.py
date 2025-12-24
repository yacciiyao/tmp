# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: AOA-06 产品优化与迭代建议（Listing 快照 + VOC 差评主题 -> Backlog；结合 constraints 限定可执行方案）

from __future__ import annotations

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
from domains.amazon_domain import AmazonProductImprovementReq


def _mysql_snapshot_evidence(row: Any, *, locator: Dict[str, Any]) -> Evidence:
    return Evidence(
        source=EvidenceSource.MYSQL,
        ref_mysql=MysqlEvidenceRef(
            table="src_amazon_product_snapshots",
            pk={"id": int(row.id)},
            fields=["asin", "title", "brand", "category", "price", "rating", "review_count", "attributes"],
            locator=dict(locator),
        ),
        excerpt=f"{row.asin} rating={row.rating} rc={row.review_count}",
    )


def _mysql_review_evidence(row: Any, *, locator: Dict[str, Any]) -> Evidence:
    return Evidence(
        source=EvidenceSource.MYSQL,
        ref_mysql=MysqlEvidenceRef(
            table="src_amazon_reviews",
            pk={"id": int(row.id)},
            fields=["asin", "rating", "title", "content", "verified", "helpful_count", "review_time"],
            locator=dict(locator),
        ),
        excerpt=str(row.content or "")[:220],
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


def _get_bool(c: Dict[str, Any], key: str, default: bool) -> bool:
    v = c.get(key, default)
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return bool(v)
    if isinstance(v, str):
        x = v.strip().lower()
        if x in ("1", "true", "yes", "y"):
            return True
        if x in ("0", "false", "no", "n"):
            return False
    return default


def _get_str_list(c: Dict[str, Any], key: str) -> List[str]:
    v = c.get(key)
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []
        # 允许逗号分隔
        return [x.strip() for x in s.split(",") if x.strip()]
    return []


def _impact_score(review: Any) -> float:
    """
    影响力打分（确定性）：
    - helpful_count 权重更高
    - rating 越低越高
    - 近似规则：helpful + (3 - rating)*2
    """
    helpful = float(review.helpful_count or 0.0) if getattr(review, "helpful_count", None) is not None else 0.0
    rating = float(review.rating or 0.0) if getattr(review, "rating", None) is not None else 0.0
    return helpful + max(0.0, (3.0 - rating)) * 2.0


def analyze_aoa06(
    *,
    req: AmazonProductImprovementReq,
    locator: Dict[str, Any],
    snapshots: List[Any],
    reviews: List[Any],
    rag_hits: Optional[List[Dict[str, Any]]],
) -> ResultSchemaV1:
    warnings: List[str] = []
    evidences: List[Evidence] = []
    recommendations: List[Recommendation] = []

    asin = str(req.query.asin).strip()
    constraints: Dict[str, Any] = dict(req.constraints or {})

    # constraints 关键开关（不强制你必须提供，但提供就生效）
    allow_structural_change = _get_bool(constraints, "allow_structural_change", True)
    allow_material_change = _get_bool(constraints, "allow_material_change", True)
    allow_packaging_change = _get_bool(constraints, "allow_packaging_change", True)
    must_have_certifications = _get_str_list(constraints, "must_have_certifications")
    forbidden_materials = _get_str_list(constraints, "forbidden_materials")
    target_cost_sensitivity = str(constraints.get("cost_sensitivity", "") or "").strip().lower()  # high/medium/low

    snap = None
    for s in snapshots:
        if str(getattr(s, "asin", "")) == asin:
            snap = s
            break

    if snap is None:
        warnings.append("target asin snapshot not found in this crawl_batch_no")

    if snap:
        ev_snap_idx = len(evidences)
        evidences.append(_mysql_snapshot_evidence(snap, locator=locator))
    else:
        ev_snap_idx = -1

    # 选择差评样本（rating<=2），并按影响力打分排序
    neg = [r for r in reviews if (float(r.rating or 0.0) if r.rating is not None else 0.0) <= 2.0]
    neg.sort(key=lambda x: (_impact_score(x), int(x.review_time or 0), int(x.id)), reverse=True)
    neg_samples = neg[:8]

    neg_evidence_idx: List[int] = []
    for r in neg_samples:
        neg_evidence_idx.append(len(evidences))
        evidences.append(_mysql_review_evidence(r, locator=locator))

    backlog: List[Dict[str, Any]] = []

    # 生成“可执行方案模板”，受 constraints 限制
    def _proposal_template(problem_text: str) -> List[str]:
        actions: List[str] = []

        # 低成本优先（cost_sensitivity=high）
        if target_cost_sensitivity == "high":
            if allow_packaging_change:
                actions.append("优先做低成本改进：补齐配件/包装防护/开箱体验，降低破损与误解")
            actions.append("优化说明书/FAQ/图片说明，降低使用门槛与误用导致的差评")
        else:
            actions.append("先从说明与体验改进切入：FAQ/图片说明/使用场景边界条件")

        if allow_structural_change:
            actions.append("如涉及结构问题：加固关键受力部位/增加限位/优化装配公差")
        else:
            actions.append("不做结构改动：通过配件/使用引导/期望管理缓解问题")

        if allow_material_change:
            if forbidden_materials:
                actions.append(f"材质调整需避开禁用材质：{', '.join(forbidden_materials[:6])}")
            actions.append("如涉及触感/耐用：选择更耐磨/更耐高温/更抗摔的材料替代方案")
        else:
            actions.append("不做材质改动：通过表面工艺/配件/保护结构优化耐用与体验")

        if must_have_certifications:
            actions.append(f"需满足认证/合规：{', '.join(must_have_certifications[:6])}（作为设计约束与文案说明）")

        # 强制确保建议可执行且不空
        if not actions:
            actions.append("基于差评样本进行快速验证：A/B 包装与说明更新，观察差评主题变化")
        return actions

    for i, r in enumerate(neg_samples, start=1):
        text = (str(r.title or "") + " " + str(r.content or "")).strip()
        text = text[:260]
        backlog.append(
            {
                "item": f"改进点-{i}",
                "impact_score": round(_impact_score(r), 2),
                "problem": text,
                "constraints_applied": {
                    "allow_structural_change": allow_structural_change,
                    "allow_material_change": allow_material_change,
                    "allow_packaging_change": allow_packaging_change,
                    "must_have_certifications": must_have_certifications,
                    "forbidden_materials": forbidden_materials,
                    "cost_sensitivity": target_cost_sensitivity or None,
                },
                "proposal_actions": _proposal_template(text),
                "evidence_index": neg_evidence_idx[i - 1],
            }
        )

    backlog.sort(key=lambda x: (-float(x["impact_score"]), x["item"]))

    if backlog:
        # 绑定证据：优先绑定目标快照 + Top3 backlog 证据
        bind_idxs: List[int] = []
        if ev_snap_idx >= 0:
            bind_idxs.append(ev_snap_idx)
        bind_idxs.extend([b["evidence_index"] for b in backlog[:3]])

        recommendations.append(
            Recommendation(
                title="基于差评影响力与约束条件生成迭代 Backlog，并按优先级推进",
                category="improvement",
                priority="P0",
                actions=[
                    "第一迭代（1-2 周）：优先做低成本高影响改动（包装/配件/说明/FAQ/图片）",
                    "第二迭代（2-6 周）：如允许结构/材质改动，针对高频根因做工程优化",
                    "同步更新 listing 表达：对已解决问题提供新卖点与图文证据，降低误解型差评",
                ],
                expected_impact="降低差评与退货，提升转化一致性与口碑",
                evidence_indexes=bind_idxs,
            )
        )
    else:
        warnings.append("no negative reviews found for backlog")
        recommendations.append(
            Recommendation(
                title="当前批次未采集到足够差评样本，建议扩大评论采样或更换批次",
                category="improvement",
                priority="P1",
                actions=["增加 review_limit 或使用更近的 crawl_batch_no 重新分析", "确认爬虫是否包含该 ASIN 的 review 数据"],
                expected_impact="避免在数据不足时做错误决策",
                evidence_indexes=([ev_snap_idx] if ev_snap_idx >= 0 else []),
            )
        )

    if rag_hits:
        evidences.append(_rag_evidence(rag_hits[0]))

    overview = {
        "site": str(req.site),
        "asin": asin,
        "snapshot_found": bool(snap),
        "review_total": len(reviews),
        "negative_sampled": len(neg_samples),
        "constraints": constraints,
    }

    insights = {
        "backlog": backlog,
        "notes": "Backlog 基于差评样本与约束条件 deterministic 生成；后续可升级为聚类/优先级模型但不改结果协议",
    }

    md = [
        f"# 产品优化与迭代建议（{req.site.upper()}）",
        "",
        f"## ASIN：{asin}",
        "",
        "## 约束条件",
    ]
    if constraints:
        for k, v in constraints.items():
            md.append(f"- {k}: {v}")
    else:
        md.append("- （无）")

    md.append("")
    md.append("## 优先改进 Backlog（Top）")
    for b in backlog[:8]:
        md.append(f"- {b['item']} (impact={b['impact_score']}): {b['problem']}")

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
            title="产品优化与迭代建议",
            summary="结合差评影响力与约束条件生成可执行的迭代 Backlog 与推进建议，并绑定证据链",
            markdown="\n".join(md),
        ),
    )
