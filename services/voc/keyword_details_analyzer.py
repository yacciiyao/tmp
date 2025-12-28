# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Keyword Analysis - keyword details from SERP snapshots

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from domains.voc_domain import KeywordSerpDataset, SerpItem
from domains.voc_output_domain import VocModuleOutput


def _safe_text(s: Optional[str], max_len: int = 180) -> Optional[str]:
    if s is None:
        return None
    t = str(s).replace("\r", " ").replace("\n", " ").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def _keyword_terms(keyword: str) -> List[str]:
    # simple split; keep alnum tokens
    parts = [p.strip().lower() for p in (keyword or "").replace("/", " ").split()]
    return [p for p in parts if p]


def _title_matches_terms(title: Optional[str], terms: Sequence[str]) -> bool:
    if not title:
        return False
    t = title.lower()
    # all terms must appear (substring)
    return all(term in t for term in terms if term)


def _serp_rank_key(it: SerpItem) -> Tuple[int, int, int]:
    # page asc, position asc, id asc
    return (int(it.page_num or 0), int(it.position or 0), int(it.kw_item_id or 0))


@dataclass
class KeywordDetailsResult:
    output: VocModuleOutput
    evidence_rows: List[Dict[str, Any]]


class KeywordDetailsAnalyzer:
    """Compute keyword-level SERP metrics.

    Data source: results.amazon_keyword_search_items (daily full crawl).

    Metrics (MVP, deterministic):
    - total_items
    - sponsored_ratio
    - avg_price
    - avg_rating
    - title_density (share of items where title contains all keyword terms)
    - serp_sales_proxy (sum of bought_past_month)
    - target_asin_share (share of items that are in target_asins)
    """

    MODULE_CODE = "keyword.keyword_details"
    SCHEMA_VERSION = 1

    @staticmethod
    def compute(
        *,
        ds: KeywordSerpDataset,
        target_asins: Sequence[str],
        top_items_per_keyword: int = 8,
        max_evidence_per_keyword: int = 20,
    ) -> KeywordDetailsResult:
        target_set = {str(a) for a in (target_asins or [])}

        items_by_kw: Dict[str, List[SerpItem]] = {}
        for it in ds.items or []:
            items_by_kw.setdefault(str(it.keyword), []).append(it)

        out_items: List[Dict[str, Any]] = []
        evidence_rows: List[Dict[str, Any]] = []

        missing_keywords: List[str] = []

        for kw in (ds.keywords or []):
            kw = str(kw)
            items = sorted(items_by_kw.get(kw, []), key=_serp_rank_key)
            if not items:
                missing_keywords.append(kw)
                continue

            total = len(items)
            sponsored = sum(1 for it in items if int(it.is_sponsored or 0) == 1)
            sponsored_ratio = round(sponsored / total, 6) if total > 0 else 0.0

            # price/rating avg
            prices = [float(it.price_amount) for it in items if it.price_amount is not None]
            avg_price = round(sum(prices) / len(prices), 4) if prices else None

            ratings = [float(it.stars) for it in items if it.stars is not None]
            avg_rating = round(sum(ratings) / len(ratings), 4) if ratings else None

            # title density
            terms = _keyword_terms(kw)
            title_hits = sum(1 for it in items if _title_matches_terms(it.title, terms))
            title_density = round(title_hits / total, 6) if total > 0 else 0.0

            # sales proxy
            sales_proxy = sum(int(it.bought_past_month or 0) for it in items if it.bought_past_month is not None)

            # target share
            if target_set:
                target_hits = sum(1 for it in items if str(it.asin) in target_set)
                target_share = round(target_hits / total, 6) if total > 0 else 0.0
            else:
                target_share = None

            # top serp rows
            top_items = []
            for it in items[:top_items_per_keyword]:
                top_items.append(
                    {
                        "kw_item_id": int(it.kw_item_id),
                        "page_num": int(it.page_num),
                        "position": int(it.position),
                        "is_sponsored": int(it.is_sponsored or 0),
                        "asin": str(it.asin),
                        "title": _safe_text(it.title, 220),
                        "brand_name": it.brand_name,
                        "price_amount": float(it.price_amount) if it.price_amount is not None else None,
                        "price_currency": it.price_currency,
                        "stars": float(it.stars) if it.stars is not None else None,
                        "review_count": int(it.review_count) if it.review_count is not None else None,
                        "bought_past_month": int(it.bought_past_month) if it.bought_past_month is not None else None,
                        "product_url": it.product_url,
                        "image_url": it.image_url,
                    }
                )

            out_items.append(
                {
                    "keyword": kw,
                    "total_items": total,
                    "sponsored_ratio": sponsored_ratio,
                    "avg_price": avg_price,
                    "avg_rating": avg_rating,
                    "title_density": title_density,
                    "serp_sales_proxy": int(sales_proxy),
                    "target_asin_share": target_share,
                    "top_items": top_items,
                }
            )

            # evidence (top N)
            for it in items[:max_evidence_per_keyword]:
                evidence_rows.append(
                    {
                        "source_type": "keyword_serp",
                        "source_id": int(it.kw_item_id),
                        "kind": "serp_item",
                        "snippet": _safe_text(it.title, 220) or "",
                        "meta_json": {
                            "keyword": kw,
                            "page_num": int(it.page_num),
                            "position": int(it.position),
                            "is_sponsored": int(it.is_sponsored or 0),
                            "asin": str(it.asin),
                            "price_amount": float(it.price_amount) if it.price_amount is not None else None,
                            "price_currency": it.price_currency,
                            "stars": float(it.stars) if it.stars is not None else None,
                            "review_count": int(it.review_count) if it.review_count is not None else None,
                            "bought_past_month": int(it.bought_past_month) if it.bought_past_month is not None else None,
                            "product_url": it.product_url,
                            "image_url": it.image_url,
                        },
                    }
                )

        available = len(out_items) > 0

        output = VocModuleOutput(
            available=available,
            module_code=KeywordDetailsAnalyzer.MODULE_CODE,
            schema_version=KeywordDetailsAnalyzer.SCHEMA_VERSION,
            data={
                "captured_day": ds.start_day or ds.end_day,
                "items": out_items,
                "missing_keywords": missing_keywords,
                "unavailable_reason": None if available else "no_keyword_serp_data",
            },
            meta={
                "site_code": ds.site_code,
                "keywords": list(ds.keywords or []),
                "target_asins": sorted(list(target_set)),
                "kw_days": {"start_day": ds.start_day, "end_day": ds.end_day},
            },
        )

        return KeywordDetailsResult(output=output, evidence_rows=evidence_rows)
