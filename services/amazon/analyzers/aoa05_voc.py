# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: AOA-05 Review/VOC 洞察（主题词频 + 好评/差评分层 + 证据样本）

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from domains.common_result_domain import Article, Evidence, EvidenceSource, MysqlEvidenceRef, Recommendation, ResultSchemaV1, RagEvidenceRef
from domains.amazon_domain import AmazonReviewVocReq

_WORD_RE = re.compile(r"[a-zA-Z0-9]+")
_SPACE_RE = re.compile(r"\s+")

_STOP = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is", "are",
    "it", "this", "that", "i", "we", "you", "they", "my", "our", "your", "as", "at",
    "was", "were", "be", "been", "but", "not", "very", "so", "from", "by", "too",
}


def _tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    text = _SPACE_RE.sub(" ", text).strip()
    toks = _WORD_RE.findall(text)
    out: List[str] = []
    for t in toks:
        if len(t) < 3:
            continue
        if t in _STOP:
            continue
        out.append(t)
    return out


def _mysql_review_evidence(row: Any, *, locator: Dict[str, Any]) -> Evidence:
    return Evidence(
        source=EvidenceSource.MYSQL,
        ref_mysql=MysqlEvidenceRef(
            table="src_amazon_reviews",
            pk={"id": int(row.id)},
            fields=["asin", "rating", "title", "content", "verified", "helpful_count", "review_time"],
            locator=dict(locator),
        ),
        excerpt=(str(row.content or "")[:220] or str(row.title or "")[:220]),
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


def analyze_aoa05(
    *,
    req: AmazonReviewVocReq,
    locator: Dict[str, Any],
    reviews: List[Any],
    rag_hits: Optional[List[Dict[str, Any]]],
) -> ResultSchemaV1:
    warnings: List[str] = []
    evidences: List[Evidence] = []
    recommendations: List[Recommendation] = []

    if not reviews:
        warnings.append("reviews is empty for this crawl_batch_no")

    neg: List[Any] = []
    pos: List[Any] = []
    neu: List[Any] = []

    for r in reviews:
        rt = float(r.rating or 0.0) if r.rating is not None else 0.0
        if rt <= 2.0:
            neg.append(r)
        elif rt >= 4.0:
            pos.append(r)
        else:
            neu.append(r)

    neg_tokens = Counter()
    pos_tokens = Counter()

    # 记录词 -> 示例 review（用于证据）
    neg_examples: Dict[str, List[Any]] = defaultdict(list)
    pos_examples: Dict[str, List[Any]] = defaultdict(list)

    for r in neg:
        toks = _tokenize(f"{r.title or ''} {r.content or ''}")
        for t in toks:
            neg_tokens[t] += 1
            if len(neg_examples[t]) < 3:
                neg_examples[t].append(r)

    for r in pos:
        toks = _tokenize(f"{r.title or ''} {r.content or ''}")
        for t in toks:
            pos_tokens[t] += 1
            if len(pos_examples[t]) < 3:
                pos_examples[t].append(r)

    top_neg = neg_tokens.most_common(15)
    top_pos = pos_tokens.most_common(15)

    # 证据：差评 Top 3 主题，每个主题绑定 1~2 条评论
    theme_items: List[Dict[str, Any]] = []
    for t, c in top_neg[:6]:
        sample = neg_examples.get(t, [])[:2]
        idxs: List[int] = []
        for r in sample:
            idxs.append(len(evidences))
            evidences.append(_mysql_review_evidence(r, locator=locator))
        theme_items.append({"theme": t, "count": c, "evidence_indexes": idxs})

    if theme_items:
        # 基于主题给出产品/包装/说明书类建议
        bind_idxs = [i for it in theme_items[:3] for i in it["evidence_indexes"][:1]]
        recommendations.append(
            Recommendation(
                title="围绕高频差评主题制定改进与解释策略（产品/包装/说明书/使用门槛）",
                category="voc",
                priority="P0",
                actions=[
                    "将 Top 差评主题转为改进 backlog（优先级：出现频次×helpful_count）",
                    "为高频误解点补充图片/视频说明与FAQ（放到 A+ 或描述）",
                    "对无法改动的点，优化期望管理：适用场景/边界条件/注意事项",
                ],
                expected_impact="降低退货与差评率，提升转化一致性",
                evidence_indexes=bind_idxs,
            )
        )

    if rag_hits:
        evidences.append(_rag_evidence(rag_hits[0]))

    overview = {
        "site": str(req.site),
        "asin": (req.query.asin or None),
        "review_total": len(reviews),
        "positive": len(pos),
        "neutral": len(neu),
        "negative": len(neg),
    }

    insights = {
        "top_negative_terms": [{"term": t, "count": c} for t, c in top_neg[:15]],
        "top_positive_terms": [{"term": t, "count": c} for t, c in top_pos[:15]],
        "negative_themes": theme_items,
        "notes": "主题基于词频（deterministic），可后续升级为聚类/LLM归纳但不改变结果协议",
    }

    md = [
        f"# Review / VOC 洞察（{req.site.upper()}）",
        "",
        "## 概览",
        f"- 评论总数：{overview['review_total']}",
        f"- 好评：{overview['positive']} / 中评：{overview['neutral']} / 差评：{overview['negative']}",
        "",
        "## 差评高频主题（Top）",
    ]
    for it in insights["negative_themes"][:10]:
        md.append(f"- {it['theme']}：{it['count']}")

    md.append("")
    md.append("## 好评高频词（Top10）")
    for it in insights["top_positive_terms"][:10]:
        md.append(f"- {it['term']}：{it['count']}")

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
            title="Amazon Review / VOC 洞察",
            summary="基于评论样本生成好评/差评主题与可执行改进建议，并绑定证据链",
            markdown="\n".join(md),
        ),
    )
