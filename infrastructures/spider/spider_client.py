# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Minimal Redis LPUSH client (RESP) for spider task enqueue.

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

from starlette import status

from domains.error_domain import AppError
from infrastructures.vconfig import vconfig
from infrastructures.vlogger import vlogger


def _resp_bulk(s: bytes) -> bytes:
    return b"$" + str(len(s)).encode("utf-8") + b"\r\n" + s + b"\r\n"


def _resp_array(parts: list[bytes]) -> bytes:
    out = b"*" + str(len(parts)).encode("utf-8") + b"\r\n"
    for p in parts:
        out += _resp_bulk(p)
    return out


async def _read_line(reader: asyncio.StreamReader, timeout: float) -> bytes:
    try:
        return await asyncio.wait_for(reader.readline(), timeout=timeout)
    except asyncio.TimeoutError as e:
        raise AppError(
            code="spider.redis_timeout",
            message="Redis read timeout",
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from e


async def _read_resp(reader: asyncio.StreamReader, timeout: float) -> Any:
    line = await _read_line(reader, timeout)
    if not line:
        raise AppError(
            code="spider.redis_closed",
            message="Redis connection closed",
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    prefix = line[:1]
    payload = line[1:-2]  # strip prefix and CRLF

    if prefix == b"+":
        return payload.decode("utf-8", errors="replace")
    if prefix == b"-":
        raise AppError(
            code="spider.redis_error",
            message=f"Redis error: {payload.decode('utf-8', errors='replace')}",
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if prefix == b":":
        try:
            return int(payload)
        except ValueError:
            return payload.decode("utf-8", errors="replace")
    if prefix == b"$":
        n = int(payload)
        if n == -1:
            return None
        data = await asyncio.wait_for(reader.readexactly(n + 2), timeout=timeout)
        return data[:-2]
    if prefix == b"*":
        count = int(payload)
        if count == -1:
            return None
        items = []
        for _ in range(count):
            items.append(await _read_resp(reader, timeout))
        return items
    return payload.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class RedisConnInfo:
    host: str
    port: int
    db: int
    password: Optional[str]


def _parse_redis_url(url: str) -> RedisConnInfo:
    u = urlparse(url)

    host = u.hostname
    port = int(u.port or 6379)
    db = 0
    if u.path and u.path != "/":
        try:
            db = int(u.path.strip("/"))
        except ValueError:
            db = 0

    password = u.password
    return RedisConnInfo(host=host, port=port, db=db, password=password)


class SpiderRedisClient:
    """Send spider requests to redis list via RESP."""

    def __init__(
        self,
        *,
        redis_url: str | None = None,
        list_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._redis_url = redis_url or str(vconfig.spider_redis_url)
        self._list_key = list_key or str(vconfig.spider_redis_list_key)
        self._timeout = float(timeout_seconds or vconfig.spider_redis_timeout_seconds)

    async def lpush_json(self, *, payload: dict[str, Any]) -> int:
        info = _parse_redis_url(self._redis_url)


def build_review_spider_payload(
    *,
    task_id: str,
    site_code: str,
    asin: str,
    callback_url: str,
    callback_token: str,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "task_id": str(task_id),
        "run_type": "amazon_review",
        "site_code": str(site_code),
        "asin": str(asin),
        "callback_url": str(callback_url),
        "callback_token": str(callback_token),
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


async def enqueue_spider_task(payload: dict[str, Any]) -> int:
    client = SpiderRedisClient()
    length = await client.lpush_json(payload=payload)
    vlogger.info(
        "spider task enqueued",
        extra={"redis_list_key": vconfig.spider_redis_list_key, "task_id": payload.get("task_id"), "len": length},
    )
    return length
