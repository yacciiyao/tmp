# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 亚马逊市场分析报告生成（基于结构化数据，便于回溯）

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructures.db.repository.amazon_repository import AmazonRepository


class AmazonReportGenerator:
    def __init__(self) -> None:
        self.repo = AmazonRepository()

    async def build_market_report(
            self,
            db: AsyncSession,
            *,
            crawl_batch_no: int,
            site: str,
            keyword: Optional[str],
            asin: Optional[str],
            category: Optional[str],
            top_n: int,
    ) -> Dict[str, Any]:
        snapshots = await self.repo.list_snapshots(db, crawl_batch_no=crawl_batch_no, site=site)
        reviews = await self.repo.list_reviews(db, crawl_batch_no=crawl_batch_no, site=site)
        metrics = await self.repo.list_keyword_metrics(db, crawl_batch_no=crawl_batch_no, site=site)

        products = self._build_product_cards(snapshots, reviews, top_n=top_n)
        kw_signals = self._build_keyword_signals(metrics)

        report: Dict[str, Any] = {
            "input": {"site": site, "keyword": keyword, "asin": asin, "category": category, "top_n": top_n},
            "crawl": {"crawl_batch_no": crawl_batch_no},
            "overview": {
                "product_count": len(products),
                "review_count": sum(p.get("review_count", 0) for p in products),
            },
            "products": products,
            "keyword_signals": kw_signals,
            "notes": [
                "报告基于爬虫结构化数据生成，所有结论均可回溯到具体 ASIN / 评论 / 关键词指标。",
                "当前版本以可解释的统计汇总为主，后续可叠加大模型进行更深层的策略推演与文案生成。",
            ],
        }
        return report

    def _build_product_cards(self, snapshots: List[Any], reviews: List[Any], *, top_n: int) -> List[Dict[str, Any]]:
        snap_by_asin: Dict[str, Any] = {}
        for s in snapshots:
            if not s.asin:
                continue
            snap_by_asin[s.asin] = s

        review_group: Dict[str, List[Any]] = {}
        for r in reviews:
            if not r.asin:
                continue
            review_group.setdefault(r.asin, []).append(r)

        # 以评分+评论数作为粗排（后续可引入更复杂的可解释排序）
        scored = []
        for asin, s in snap_by_asin.items():
            rating = float(s.rating or 0.0)
            review_count = int(s.review_count or 0)
            scored.append((rating, review_count, asin))
        scored.sort(reverse=True)

        cards: List[Dict[str, Any]] = []
        for _, __, asin in scored[: max(1, top_n)]:
            s = snap_by_asin[asin]
            asin_reviews = review_group.get(asin, [])

            cards.append(
                {
                    "asin": asin,
                    "title": s.title,
                    "brand": s.brand,
                    "price": float(s.price) if s.price is not None else None,
                    "rating": float(s.rating) if s.rating is not None else None,
                    "review_count": int(s.review_count or 0),
                    "bsr": s.bsr,
                    "categories": s.categories,
                    "features": s.features,
                    "top_review_themes": self._extract_review_themes(asin_reviews),
                }
            )
        return cards

    @staticmethod
    def _extract_review_themes(reviews: List[Any]) -> List[Dict[str, Any]]:
        # 简单词频：用于离线验证与可解释展示（不依赖额外NLP库）
        text = " ".join([(r.title or "") + " " + (r.content or "") for r in reviews])
        tokens = [t.strip().lower() for t in text.replace("\n", " ").split(" ") if t.strip()]
        tokens = [t for t in tokens if len(t) >= 4]

        top = Counter(tokens).most_common(12)
        return [{"token": k, "count": int(v)} for k, v in top]

    @staticmethod
    def _build_keyword_signals(metrics: List[Any]) -> Dict[str, Any]:
        if not metrics:
            return {"keywords": [], "summary": {"count": 0}}

        rows = []
        for m in metrics:
            rows.append(
                {
                    "keyword": m.keyword,
                    "search_volume": float(m.search_volume) if m.search_volume is not None else None,
                    "cpc": float(m.cpc) if m.cpc is not None else None,
                    "competition": float(m.competition) if m.competition is not None else None,
                }
            )

        rows_sorted = sorted(rows, key=lambda x: (x["search_volume"] or 0.0), reverse=True)[:30]
        return {"keywords": rows_sorted, "summary": {"count": len(rows), "top_keyword": rows_sorted[0]["keyword"]}}
