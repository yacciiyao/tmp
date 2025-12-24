# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: ResultSchemaV1 结果质量评估（不做兼容/不吞错；用于产出告警与基础质量指标）

from __future__ import annotations

from typing import List

from domains.common_result_domain import ResultSchemaV1


class ResultEvaluator:
    """
    只做“质量告警”，不改变 schema，不引入不确定性：
    - P0/high 建议必须绑定证据
    - article.markdown 过短提示
    - insights 为空提示
    """

    @staticmethod
    def evaluate(result: ResultSchemaV1) -> List[str]:
        warnings: List[str] = []

        # 1) P0/high 建议必须绑定证据
        for i, rec in enumerate(result.recommendations):
            pri = (rec.priority or "").lower()
            if pri in ("p0", "high"):
                if not rec.evidence_indexes:
                    warnings.append(f"recommendations[{i}] priority={rec.priority} missing evidence_indexes")

        # 2) insights 为空提示（不失败，真实业务允许数据不足）
        if not result.insights:
            warnings.append("insights is empty")

        # 3) article 过短提示
        md = (result.article.markdown or "").strip()
        if md and len(md) < 120:
            warnings.append("article.markdown is too short (<120 chars)")

        return warnings
