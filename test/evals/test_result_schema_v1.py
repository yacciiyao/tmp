# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: ResultSchemaV1 最小回归评测（schema 合规 + 证据绑定 + 质量告警）

from __future__ import annotations

import pytest

from domains.common_result_domain import (
    Article,
    Evidence,
    EvidenceSource,
    MysqlEvidenceRef,
    Recommendation,
    ResultSchemaV1,
)
from services.common.result_evaluator import ResultEvaluator


def test_result_schema_v1_ok() -> None:
    r = ResultSchemaV1(
        biz="amazon",
        task_kind="AOA-04",
        input={"site": "us"},
        crawl={"crawl_batch_no": 1, "site": "us"},
        overview={"asin": "B000TEST"},
        insights={"rules": [{"rule": "title_length", "level": "ok"}]},
        evidences=[
            Evidence(
                source=EvidenceSource.MYSQL,
                ref_mysql=MysqlEvidenceRef(
                    table="src_amazon_product_snapshots",
                    pk={"id": 1},
                    fields=["asin", "title"],
                    locator={"crawl_batch_no": 1, "site": "us"},
                ),
                excerpt="B000TEST title_len=120",
            )
        ],
        recommendations=[
            Recommendation(
                title="优化标题关键词覆盖",
                category="listing",
                priority="P0",
                actions=["补齐核心关键词"],
                evidence_indexes=[0],
            )
        ],
        article=Article(title="t", summary="s", markdown="# hi\n\ncontent...\n" * 10),
    )

    # schema 本身应通过
    assert r.biz == "amazon"
    assert r.recommendations[0].evidence_indexes == [0]

    # evaluator 仅输出告警，不应报错
    warns = ResultEvaluator.evaluate(r)
    assert isinstance(warns, list)


def test_result_schema_v1_out_of_range_should_fail() -> None:
    with pytest.raises(ValueError):
        ResultSchemaV1(
            biz="amazon",
            task_kind="AOA-01",
            evidences=[],
            recommendations=[
                Recommendation(
                    title="bad",
                    category="x",
                    priority="P0",
                    actions=[],
                    evidence_indexes=[0],  # out of range
                )
            ],
        )


def test_result_evaluator_warn_missing_evidence_for_p0() -> None:
    r = ResultSchemaV1(
        biz="amazon",
        task_kind="AOA-05",
        overview={"review_total": 10},
        insights={"top_negative_terms": []},
        recommendations=[
            Recommendation(
                title="缺证据示例",
                category="voc",
                priority="P0",
                actions=["..."],
                evidence_indexes=[],
            )
        ],
    )
    warns = ResultEvaluator.evaluate(r)
    assert any("missing evidence_indexes" in w for w in warns)
