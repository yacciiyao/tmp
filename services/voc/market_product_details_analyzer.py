# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Market Insight - product details (listing snapshot)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from domains.voc_domain import ListingDataset, ListingSnapshot
from domains.voc_output_domain import VocModuleOutput


def _safe_text(s: Optional[str], max_len: int = 180) -> Optional[str]:
    if s is None:
        return None
    t = str(s).replace("\r", " ").replace("\n", " ").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def _pick_latest_snapshot(snapshots: Sequence[ListingSnapshot]) -> Optional[ListingSnapshot]:
    if not snapshots:
        return None
    # captured_at desc, listing_id desc
    return sorted(snapshots, key=lambda x: (int(x.captured_at or 0), int(x.listing_id or 0)), reverse=True)[0]


@dataclass
class MarketProductDetailsResult:
    output: VocModuleOutput
    evidence_rows: List[Dict[str, Any]]


class MarketProductDetailsAnalyzer:
    """Produce a product details table from listing snapshot data.

    Data source: results.amazon_listing_items (+ attributes/bullets/media joined in SpiderResultsRepository).

    Output is deterministic and meant for Market Insight basic table.
    """

    MODULE_CODE = "market.product_details"
    SCHEMA_VERSION = 1

    @staticmethod
    def compute(
        *,
        ds: ListingDataset,
        target_asins: Sequence[str],
        competitor_asins: Sequence[str],
        max_evidence: int = 100,
    ) -> MarketProductDetailsResult:
        target_set = {str(a) for a in (target_asins or [])}
        competitor_set = {str(a) for a in (competitor_asins or [])}
        all_asins: List[str] = sorted({*target_set, *competitor_set} | {str(a) for a in (ds.asins or [])})

        snaps_by_asin: Dict[str, List[ListingSnapshot]] = {}
        for s in ds.snapshots or []:
            snaps_by_asin.setdefault(str(s.asin), []).append(s)

        rows: List[Dict[str, Any]] = []
        missing: List[str] = []
        evidence_rows: List[Dict[str, Any]] = []

        for asin in all_asins:
            snap = _pick_latest_snapshot(snaps_by_asin.get(asin, []))
            if snap is None:
                missing.append(asin)
                continue

            group = "target" if asin in target_set else ("competitor" if asin in competitor_set else "other")

            row = {
                "asin": asin,
                "group": group,
                "captured_day": snap.captured_day,
                "title": _safe_text(snap.title, 220),
                "brand_name": snap.brand_name,
                "price_amount": float(snap.price_amount) if snap.price_amount is not None else None,
                "price_currency": snap.price_currency,
                "stars": float(snap.stars) if snap.stars is not None else None,
                "ratings_count": int(snap.ratings_count) if snap.ratings_count is not None else None,
                "review_count": int(snap.review_count) if snap.review_count is not None else None,
                "bought_past_month": int(snap.bought_past_month) if snap.bought_past_month is not None else None,
                "availability_text": _safe_text(snap.availability_text, 120),
                "seller_name": snap.seller_name,
                "variation_summary": _safe_text(snap.variation_summary, 140),
                "category_path": _safe_text(snap.category_path, 180),
                "main_image_url": snap.main_image_url,
                "listing_id": int(snap.listing_id),
            }
            rows.append(row)

            if len(evidence_rows) < max_evidence:
                evidence_rows.append(
                    {
                        "source_type": "listing",
                        "source_id": int(snap.listing_id),
                        "kind": "listing_snapshot",
                        "snippet": _safe_text(snap.title, 220) or "",
                        "meta_json": {
                            "asin": asin,
                            "group": group,
                            "captured_day": snap.captured_day,
                            "price_amount": float(snap.price_amount) if snap.price_amount is not None else None,
                            "price_currency": snap.price_currency,
                            "stars": float(snap.stars) if snap.stars is not None else None,
                            "review_count": int(snap.review_count) if snap.review_count is not None else None,
                            "bought_past_month": int(snap.bought_past_month) if snap.bought_past_month is not None else None,
                            "main_image_url": snap.main_image_url,
                        },
                    }
                )

        available = len(rows) > 0
        output = VocModuleOutput(
            available=available,
            module_code=MarketProductDetailsAnalyzer.MODULE_CODE,
            schema_version=MarketProductDetailsAnalyzer.SCHEMA_VERSION,
            data={
                "captured_day": ds.start_day or ds.end_day,
                "rows": rows,
                "missing_asins": missing,
                "unavailable_reason": None if available else "no_listing_data",
            },
            meta={
                "site_code": ds.site_code,
                "target_asins": sorted(list(target_set)),
                "competitor_asins": sorted(list(competitor_set)),
                "listing_days": {
                    "start_day": ds.start_day,
                    "end_day": ds.end_day,
                },
            },
        )

        return MarketProductDetailsResult(output=output, evidence_rows=evidence_rows)
