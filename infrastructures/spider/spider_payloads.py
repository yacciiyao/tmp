# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Build spider enqueue payloads for VOC.

from __future__ import annotations

from typing import Any, Optional


def build_spider_task_payload(
    *,
    task_id: str,
    run_type: str,
    site_code: str,
    scope_type: str,
    scope_value: str,
    callback_url: str,
    callback_token: str,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a minimal spider enqueue payload.

    Notes:
        - This payload shape matches the existing SpiderRedisClient enqueue usage in this project.
        - If spider system requires richer schema (platform/biz_type/plan_json), extend this
          builder but keep backward compatibility.
    """

    payload: dict[str, Any] = {
        "task_id": str(task_id),
        "run_type": str(run_type),
        "site_code": str(site_code),
        "scope_type": str(scope_type),
        "scope_value": str(scope_value),
        "callback_url": str(callback_url),
        "callback_token": str(callback_token),
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def build_review_payload(
    *,
    task_id: str,
    site_code: str,
    asin: str,
    callback_url: str,
    callback_token: str,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return build_spider_task_payload(
        task_id=task_id,
        run_type="amazon_review",
        site_code=site_code,
        scope_type="asin",
        scope_value=asin,
        callback_url=callback_url,
        callback_token=callback_token,
        extra=extra,
    )


def build_listing_payload(
    *,
    task_id: str,
    site_code: str,
    asin: str,
    callback_url: str,
    callback_token: str,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return build_spider_task_payload(
        task_id=task_id,
        run_type="amazon_listing",
        site_code=site_code,
        scope_type="asin",
        scope_value=asin,
        callback_url=callback_url,
        callback_token=callback_token,
        extra=extra,
    )


def build_keyword_payload(
    *,
    task_id: str,
    site_code: str,
    keyword: str,
    callback_url: str,
    callback_token: str,
    page_num: int = 1,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ex = dict(extra or {})
    ex.setdefault("page_num", int(page_num))
    return build_spider_task_payload(
        task_id=task_id,
        run_type="amazon_keyword_search",
        site_code=site_code,
        scope_type="keyword",
        scope_value=keyword,
        callback_url=callback_url,
        callback_token=callback_token,
        extra=ex,
    )
