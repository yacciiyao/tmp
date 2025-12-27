# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Read-only repository for spider(results) DB.

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.voc_domain import (
    KeywordSerpDataset,
    ListingDataset,
    ListingAttribute,
    ListingBullet,
    ListingMedia,
    ListingSnapshot,
    Review,
    ReviewDataset,
    ReviewMedia,
    ReviewOption,
    SerpItem,
)

from infrastructures.db.spider_orm.spider_results_orm import (
    AmazonKeywordSearchItemsORM,
    AmazonListingAttributesORM,
    AmazonListingBulletsORM,
    AmazonListingItemsORM,
    AmazonListingMediaORM,
    AmazonReviewItemsORM,
    AmazonReviewMediaORM,
    AmazonReviewObservationsORM,
    AmazonReviewOptionsORM,
    SpiderRunsORM,
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _chunked(items: Iterable[str], chunk_size: int) -> List[List[str]]:
    buf: List[str] = []
    out: List[List[str]] = []
    for x in items:
        buf.append(str(x))
        if len(buf) >= chunk_size:
            out.append(buf)
            buf = []
    if buf:
        out.append(buf)
    return out


def _day_from_epoch_utc(ts: int) -> str:
    # v1.0 freezes captured_day derivation to UTC day.
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def _day_bounds_epoch_utc(day: str) -> Tuple[int, int]:
    # [start, end) in epoch seconds
    dt = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start = int(dt.timestamp())
    end = int((dt + timedelta(days=1)).timestamp())
    return start, end


def _maybe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Repository
# -----------------------------------------------------------------------------


class SpiderResultsRepository:
    """Read-only accessors for spider(results) DB.

    This repository is the ONLY place allowed to:
      - decide data selection strategy (latest day / latest common day)
      - join denormalized results tables
      - map ORM rows into VOC domain datasets
    """

    # -----------------------------
    # Meta
    # -----------------------------

    @staticmethod
    async def get_run(db: AsyncSession, *, run_id: int) -> Optional[SpiderRunsORM]:
        stmt = select(SpiderRunsORM).where(SpiderRunsORM.run_id == int(run_id))
        res = await db.execute(stmt)
        return res.scalars().first()

    # -----------------------------
    # Reviews
    # -----------------------------

    @staticmethod
    async def count_reviews_by_run(db: AsyncSession, *, run_id: int) -> int:
        """Count reviews observed in a specific spider run.

        Note: amazon_review_items does NOT have run_id. We must count from observations.
        """
        stmt = select(func.count()).select_from(AmazonReviewObservationsORM).where(AmazonReviewObservationsORM.run_id == int(run_id))
        res = await db.execute(stmt)
        return int(res.scalar_one() or 0)

    @staticmethod
    async def list_reviews_by_run(
        db: AsyncSession,
        *,
        run_id: int,
        limit: int = 1000,
        offset: int = 0,
        order_by_position: bool = True,
    ) -> List[AmazonReviewItemsORM]:
        """List review items observed in a run, ordered by (page_num, position)."""

        obs = AmazonReviewObservationsORM
        itm = AmazonReviewItemsORM
        stmt = (
            select(itm)
            .join(obs, obs.review_id == itm.review_id)
            .where(obs.run_id == int(run_id))
        )
        if order_by_position:
            stmt = stmt.order_by(obs.page_num.asc(), obs.position.asc())
        else:
            stmt = stmt.order_by(itm.review_id.asc())
        stmt = stmt.limit(int(limit)).offset(int(offset))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_review_media(db: AsyncSession, *, review_ids: Sequence[int], chunk_size: int = 500) -> List[AmazonReviewMediaORM]:
        if not review_ids:
            return []
        out: List[AmazonReviewMediaORM] = []
        for chunk in _chunked([str(x) for x in review_ids], chunk_size):
            ids = [int(x) for x in chunk]
            stmt = select(AmazonReviewMediaORM).where(AmazonReviewMediaORM.review_id.in_(ids)).order_by(AmazonReviewMediaORM.review_id.asc(), AmazonReviewMediaORM.media_id.asc())
            res = await db.execute(stmt)
            out.extend(list(res.scalars().all()))
        return out

    @staticmethod
    async def list_review_options(db: AsyncSession, *, review_ids: Sequence[int], chunk_size: int = 500) -> List[AmazonReviewOptionsORM]:
        if not review_ids:
            return []
        out: List[AmazonReviewOptionsORM] = []
        for chunk in _chunked([str(x) for x in review_ids], chunk_size):
            ids = [int(x) for x in chunk]
            stmt = select(AmazonReviewOptionsORM).where(AmazonReviewOptionsORM.review_id.in_(ids)).order_by(AmazonReviewOptionsORM.review_id.asc(), AmazonReviewOptionsORM.option_id.asc())
            res = await db.execute(stmt)
            out.extend(list(res.scalars().all()))
        return out

    @staticmethod
    async def load_review_dataset(
        db: AsyncSession,
        *,
        site_code: str,
        asins: Sequence[str],
        review_time_from: Optional[int] = None,
        review_time_to: Optional[int] = None,
        preferred_task_id: Optional[int] = None,
        preferred_run_id: Optional[int] = None,
        chunk_size: int = 500,
    ) -> ReviewDataset:
        """Load reviews for VOC analysis.

        Selection strategy (frozen):
        - If preferred_run_id is provided: use amazon_review_observations to restrict review_ids.
        - Otherwise: use all reviews by (site_code, asin) in results (deduped by design).
        - If review_time_from/to provided, only include reviews with non-null review_time in range.
        """

        site_code = str(site_code)
        asins = [str(a) for a in asins]

        itm = AmazonReviewItemsORM
        obs = AmazonReviewObservationsORM

        stmt = select(itm).where(itm.site_code == site_code, itm.asin.in_(asins))

        if preferred_run_id is not None or preferred_task_id is not None:
            conds = [obs.site_code == site_code, obs.asin.in_(asins)]
            if preferred_run_id is not None:
                conds.append(obs.run_id == int(preferred_run_id))
            if preferred_task_id is not None:
                conds.append(obs.task_id == int(preferred_task_id))
            stmt = select(itm).join(obs, obs.review_id == itm.review_id).where(and_(*conds))

        if review_time_from is not None or review_time_to is not None:
            # enforce spec: unknown review_time can't be placed into window => exclude
            stmt = stmt.where(itm.review_time.is_not(None))
            if review_time_from is not None:
                stmt = stmt.where(itm.review_time >= int(review_time_from))
            if review_time_to is not None:
                stmt = stmt.where(itm.review_time <= int(review_time_to))

        res = await db.execute(stmt)
        rows = list(res.scalars().all())

        review_ids = [r.review_id for r in rows]
        media_rows = await SpiderResultsRepository.list_review_media(db, review_ids=review_ids, chunk_size=chunk_size)
        option_rows = await SpiderResultsRepository.list_review_options(db, review_ids=review_ids, chunk_size=chunk_size)

        media_by_review: Dict[int, List[ReviewMedia]] = {}
        for m in media_rows:
            media_by_review.setdefault(m.review_id, []).append(
                ReviewMedia(
                    media_type=str(m.media_type),
                    media_url=str(m.media_url),
                    thumb_url=str(m.thumb_url) if m.thumb_url is not None else None,
                    created_at=int(m.created_at) if m.created_at is not None else None,
                )
            )

        opts_by_review: Dict[int, List[ReviewOption]] = {}
        for o in option_rows:
            opts_by_review.setdefault(o.review_id, []).append(ReviewOption(option_name=str(o.option_name), option_value=str(o.option_value)))

        reviews: List[Review] = []
        for r in rows:
            reviews.append(
                Review(
                    review_id=int(r.review_id),
                    site_code=str(r.site_code),
                    asin=str(r.asin),
                    review_external_id=str(r.review_external_id) if r.review_external_id is not None else None,
                    item_fingerprint=str(r.item_fingerprint),
                    stars=int(r.stars),
                    review_title=str(r.review_title) if r.review_title is not None else None,
                    review_body=str(r.review_body) if r.review_body is not None else None,
                    language_code=str(r.language_code) if r.language_code is not None else None,
                    reviewer_name=str(r.reviewer_name) if r.reviewer_name is not None else None,
                    review_location=str(r.review_location) if r.review_location is not None else None,
                    review_time=int(r.review_time) if r.review_time is not None else None,
                    helpful_votes=int(r.helpful_votes or 0),
                    verified_purchase=int(r.verified_purchase or 0),
                    options_text=str(r.options_text) if r.options_text is not None else None,
                    review_url=str(r.review_url) if r.review_url is not None else None,
                    created_at=int(r.created_at) if r.created_at is not None else None,
                    updated_at=int(r.updated_at) if r.updated_at is not None else None,
                    options=opts_by_review.get(int(r.review_id), []),
                    media=media_by_review.get(int(r.review_id), []),
                )
            )

        return ReviewDataset(
            site_code=site_code,
            asins=asins,
            review_time_from=review_time_from,
            review_time_to=review_time_to,
            reviews=reviews,
        )

    # -----------------------------
    # Listings
    # -----------------------------

    @staticmethod
    async def _latest_listing_ts_by_asin(db: AsyncSession, *, site_code: str, asins: Sequence[str]) -> Dict[str, int]:
        stmt = (
            select(AmazonListingItemsORM.asin, func.max(AmazonListingItemsORM.captured_at))
            .where(AmazonListingItemsORM.site_code == str(site_code), AmazonListingItemsORM.asin.in_([str(a) for a in asins]))
            .group_by(AmazonListingItemsORM.asin)
        )
        res = await db.execute(stmt)
        out: Dict[str, int] = {}
        for asin, ts in res.all():
            if ts is not None:
                out[str(asin)] = int(ts)
        return out

    @staticmethod
    async def _pick_latest_common_day(db: AsyncSession, *, site_code: str, asins: Sequence[str]) -> Optional[str]:
        latest = await SpiderResultsRepository._latest_listing_ts_by_asin(db, site_code=site_code, asins=asins)
        if not latest or len(latest) < 1:
            return None
        days = [_day_from_epoch_utc(ts) for ts in latest.values()]
        return min(days) if days else None

    @staticmethod
    async def load_listing_dataset(
        db: AsyncSession,
        *,
        site_code: str,
        asins: Sequence[str],
        preferred_task_id: Optional[int] = None,
        preferred_run_id: Optional[int] = None,
        mode: str = "latest_common_day",
        day: Optional[str] = None,
        start_day: Optional[str] = None,
        end_day: Optional[str] = None,
    ) -> ListingDataset:
        """Load listing snapshots.

        Modes:
        - latest_common_day (default): choose a single captured_day that all ASINs most likely have.
        - day: explicit captured_day
        - range: explicit [start_day, end_day] inclusive

        If preferred_run_id/task_id provided: restrict to that run/task (single snapshot per asin expected).
        """

        site_code = str(site_code)
        asins = [str(a) for a in asins]

        chosen_start_day: Optional[str] = None
        chosen_end_day: Optional[str] = None

        base_stmt = select(AmazonListingItemsORM).where(AmazonListingItemsORM.site_code == site_code, AmazonListingItemsORM.asin.in_(asins))

        if preferred_run_id is not None:
            base_stmt = base_stmt.where(AmazonListingItemsORM.run_id == int(preferred_run_id))
        if preferred_task_id is not None:
            base_stmt = base_stmt.where(AmazonListingItemsORM.task_id == int(preferred_task_id))

        if mode == "latest_common_day":
            d = await SpiderResultsRepository._pick_latest_common_day(db, site_code=site_code, asins=asins)
            if d is None:
                return ListingDataset(site_code=site_code, asins=asins, snapshots=[])
            day = d
            mode = "day"

        if mode == "day":
            assert day is not None
            chosen_start_day = day
            chosen_end_day = day
            start_ts, end_ts = _day_bounds_epoch_utc(day)
            base_stmt = base_stmt.where(AmazonListingItemsORM.captured_at >= start_ts, AmazonListingItemsORM.captured_at < end_ts)

        elif mode == "range":
            assert start_day is not None and end_day is not None
            chosen_start_day = start_day
            chosen_end_day = end_day
            start_ts, _ = _day_bounds_epoch_utc(start_day)
            _, end_ts = _day_bounds_epoch_utc(end_day)
            base_stmt = base_stmt.where(AmazonListingItemsORM.captured_at >= start_ts, AmazonListingItemsORM.captured_at < end_ts)
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        # order newest first so we can dedup by (asin, captured_day)
        base_stmt = base_stmt.order_by(AmazonListingItemsORM.captured_at.desc(), AmazonListingItemsORM.listing_id.desc())
        res = await db.execute(base_stmt)
        rows = list(res.scalars().all())

        # Dedup: keep latest per (asin, captured_day)
        chosen: Dict[Tuple[str, str], AmazonListingItemsORM] = {}
        for r in rows:
            d = _day_from_epoch_utc(int(r.captured_at))
            key = (str(r.asin), d)
            if key not in chosen:
                chosen[key] = r

        chosen_rows = list(chosen.values())
        listing_ids = [int(r.listing_id) for r in chosen_rows]

        attrs_by_listing: Dict[int, List[ListingAttribute]] = {}
        bullets_by_listing: Dict[int, List[ListingBullet]] = {}
        media_by_listing: Dict[int, List[ListingMedia]] = {}

        if listing_ids:
            # attributes
            stmt = select(AmazonListingAttributesORM).where(AmazonListingAttributesORM.listing_id.in_(listing_ids))
            res = await db.execute(stmt)
            for a in res.scalars().all():
                attrs_by_listing.setdefault(int(a.listing_id), []).append(ListingAttribute(attr_name=str(a.attr_name), attr_value=str(a.attr_value)))

            # bullets
            stmt = select(AmazonListingBulletsORM).where(AmazonListingBulletsORM.listing_id.in_(listing_ids)).order_by(
                AmazonListingBulletsORM.listing_id.asc(), AmazonListingBulletsORM.bullet_index.asc()
            )
            res = await db.execute(stmt)
            for b in res.scalars().all():
                bullets_by_listing.setdefault(int(b.listing_id), []).append(ListingBullet(bullet_index=int(b.bullet_index), bullet_text=str(b.bullet_text)))

            # media
            stmt = select(AmazonListingMediaORM).where(AmazonListingMediaORM.listing_id.in_(listing_ids)).order_by(
                AmazonListingMediaORM.listing_id.asc(), AmazonListingMediaORM.position.asc(), AmazonListingMediaORM.media_id.asc()
            )
            res = await db.execute(stmt)
            for m in res.scalars().all():
                media_by_listing.setdefault(int(m.listing_id), []).append(
                    ListingMedia(media_type=str(m.media_type), media_url=str(m.media_url), position=int(m.position or 0))
                )

        snapshots: List[ListingSnapshot] = []
        for r in chosen_rows:
            d = _day_from_epoch_utc(int(r.captured_at))
            snapshots.append(
                ListingSnapshot(
                    listing_id=int(r.listing_id),
                    task_id=int(r.task_id),
                    run_id=int(r.run_id),
                    captured_at=int(r.captured_at),
                    captured_day=d,
                    site_code=str(r.site_code),
                    asin=str(r.asin),
                    parent_asin=str(r.parent_asin) if r.parent_asin is not None else None,
                    brand_name=str(r.brand_name) if r.brand_name is not None else None,
                    title=str(r.title) if r.title is not None else None,
                    about_text=str(r.about_text) if r.about_text is not None else None,
                    product_information_text=str(r.product_information_text) if r.product_information_text is not None else None,
                    main_image_url=str(r.main_image_url) if r.main_image_url is not None else None,
                    price_amount=_maybe_float(r.price_amount),
                    price_currency=str(r.price_currency) if r.price_currency is not None else None,
                    stars=_maybe_float(r.stars),
                    ratings_count=int(r.ratings_count) if r.ratings_count is not None else None,
                    review_count=int(r.review_count) if r.review_count is not None else None,
                    bought_past_month=int(r.bought_past_month) if r.bought_past_month is not None else None,
                    availability_text=str(r.availability_text) if r.availability_text is not None else None,
                    seller_name=str(r.seller_name) if r.seller_name is not None else None,
                    variation_summary=str(r.variation_summary) if r.variation_summary is not None else None,
                    category_path=str(r.category_path) if r.category_path is not None else None,
                    attributes=attrs_by_listing.get(int(r.listing_id), []),
                    bullets=bullets_by_listing.get(int(r.listing_id), []),
                    media=media_by_listing.get(int(r.listing_id), []),
                )
            )

        return ListingDataset(site_code=site_code, asins=asins, start_day=chosen_start_day, end_day=chosen_end_day, snapshots=snapshots)

    # -----------------------------
    # Keyword SERP
    # -----------------------------

    @staticmethod
    async def _latest_kw_ts_by_keyword(db: AsyncSession, *, site_code: str, keywords: Sequence[str]) -> Dict[str, int]:
        stmt = (
            select(AmazonKeywordSearchItemsORM.keyword, func.max(AmazonKeywordSearchItemsORM.captured_at))
            .where(AmazonKeywordSearchItemsORM.site_code == str(site_code), AmazonKeywordSearchItemsORM.keyword.in_([str(k) for k in keywords]))
            .group_by(AmazonKeywordSearchItemsORM.keyword)
        )
        res = await db.execute(stmt)
        out: Dict[str, int] = {}
        for kw, ts in res.all():
            if ts is not None:
                out[str(kw)] = int(ts)
        return out

    @staticmethod
    async def _pick_latest_common_day_kw(db: AsyncSession, *, site_code: str, keywords: Sequence[str]) -> Optional[str]:
        latest = await SpiderResultsRepository._latest_kw_ts_by_keyword(db, site_code=site_code, keywords=keywords)
        if not latest:
            return None
        days = [_day_from_epoch_utc(ts) for ts in latest.values()]
        return min(days) if days else None

    @staticmethod
    async def load_keyword_serp_dataset(
        db: AsyncSession,
        *,
        site_code: str,
        keywords: Sequence[str],
        preferred_task_id: Optional[int] = None,
        preferred_run_id: Optional[int] = None,
        mode: str = "latest_common_day",
        day: Optional[str] = None,
        start_day: Optional[str] = None,
        end_day: Optional[str] = None,
        max_page_num: Optional[int] = None,
    ) -> KeywordSerpDataset:
        site_code = str(site_code)
        keywords = [str(k) for k in keywords]

        chosen_start_day: Optional[str] = None
        chosen_end_day: Optional[str] = None

        stmt = select(AmazonKeywordSearchItemsORM).where(
            AmazonKeywordSearchItemsORM.site_code == site_code,
            AmazonKeywordSearchItemsORM.keyword.in_(keywords),
        )
        if preferred_run_id is not None:
            stmt = stmt.where(AmazonKeywordSearchItemsORM.run_id == int(preferred_run_id))
        if preferred_task_id is not None:
            stmt = stmt.where(AmazonKeywordSearchItemsORM.task_id == int(preferred_task_id))

        if mode == "latest_common_day":
            d = await SpiderResultsRepository._pick_latest_common_day_kw(db, site_code=site_code, keywords=keywords)
            if d is None:
                return KeywordSerpDataset(site_code=site_code, keywords=keywords, items=[])
            day = d
            mode = "day"

        if mode == "day":
            assert day is not None
            chosen_start_day = day
            chosen_end_day = day
            start_ts, end_ts = _day_bounds_epoch_utc(day)
            stmt = stmt.where(AmazonKeywordSearchItemsORM.captured_at >= start_ts, AmazonKeywordSearchItemsORM.captured_at < end_ts)
        elif mode == "range":
            assert start_day is not None and end_day is not None
            chosen_start_day = start_day
            chosen_end_day = end_day
            start_ts, _ = _day_bounds_epoch_utc(start_day)
            _, end_ts = _day_bounds_epoch_utc(end_day)
            stmt = stmt.where(AmazonKeywordSearchItemsORM.captured_at >= start_ts, AmazonKeywordSearchItemsORM.captured_at < end_ts)
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        if max_page_num is not None:
            stmt = stmt.where(AmazonKeywordSearchItemsORM.page_num <= int(max_page_num))

        # newest first for dedup by (kw, day, page, position)
        stmt = stmt.order_by(AmazonKeywordSearchItemsORM.captured_at.desc(), AmazonKeywordSearchItemsORM.kw_item_id.desc())
        res = await db.execute(stmt)
        rows = list(res.scalars().all())

        chosen: Dict[Tuple[str, str, int, int], AmazonKeywordSearchItemsORM] = {}
        for r in rows:
            d = _day_from_epoch_utc(int(r.captured_at))
            key = (str(r.keyword), d, int(r.page_num), int(r.position))
            if key not in chosen:
                chosen[key] = r

        items: List[SerpItem] = []
        for r in chosen.values():
            d = _day_from_epoch_utc(int(r.captured_at))
            items.append(
                SerpItem(
                    kw_item_id=int(r.kw_item_id),
                    task_id=int(r.task_id),
                    run_id=int(r.run_id),
                    captured_at=int(r.captured_at),
                    captured_day=d,
                    site_code=str(r.site_code),
                    keyword=str(r.keyword),
                    page_num=int(r.page_num),
                    position=int(r.position),
                    is_sponsored=int(r.is_sponsored or 0),
                    asin=str(r.asin),
                    title=str(r.title) if r.title is not None else None,
                    brand_name=str(r.brand_name) if r.brand_name is not None else None,
                    image_url=str(r.image_url) if r.image_url is not None else None,
                    product_url=str(r.product_url) if r.product_url is not None else None,
                    price_amount=_maybe_float(r.price_amount),
                    price_currency=str(r.price_currency) if r.price_currency is not None else None,
                    stars=_maybe_float(r.stars),
                    ratings_count=int(r.ratings_count) if r.ratings_count is not None else None,
                    review_count=int(r.review_count) if r.review_count is not None else None,
                    bought_past_month=int(r.bought_past_month) if r.bought_past_month is not None else None,
                )
            )

        return KeywordSerpDataset(site_code=site_code, keywords=keywords, start_day=chosen_start_day, end_day=chosen_end_day, items=items)
