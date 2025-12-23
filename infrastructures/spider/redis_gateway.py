# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: Redis 网关（用于将爬虫任务入队到外部爬虫服务）
from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import unquote, urlparse


def _resp_bulk(data: bytes) -> bytes:
    return b"$%d\r\n%s\r\n" % (len(data), data)


def _resp_array(items: list[bytes]) -> bytes:
    buf = [b"*%d\r\n" % len(items)]
    buf.extend(_resp_bulk(x) for x in items)
    return b"".join(buf)


def _read_line(sock: socket.socket) -> bytes:
    data = bytearray()
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("Redis connection closed")
        data += chunk
        if len(data) >= 2 and data[-2:] == b"\r\n":
            return bytes(data[:-2])


def _expect_ok(sock: socket.socket) -> None:
    line = _read_line(sock)
    if not line:
        raise ConnectionError("Redis empty reply")
    if line[:1] == b"+":
        return
    raise ConnectionError(f"Redis error reply: {line!r}")


def _read_int(sock: socket.socket) -> int:
    line = _read_line(sock)
    if not line:
        raise ConnectionError("Redis empty reply")
    if line[:1] == b":":
        return int(line[1:].decode("utf-8"))
    raise ConnectionError(f"Redis unexpected reply: {line!r}")


@dataclass(frozen=True)
class RedisConnInfo:
    host: str
    port: int
    db: int
    username: Optional[str]
    password: Optional[str]
    timeout_seconds: float


def parse_redis_url(redis_url: str, timeout_seconds: float) -> RedisConnInfo:
    info = urlparse(redis_url)
    if info.scheme != "redis":
        raise ValueError("SPIDER_REDIS_URL must start with redis://")

    host = info.hostname or "localhost"
    port = info.port or 6379

    path = info.path.lstrip("/")
    db = int(path) if path else 0

    username = unquote(info.username) if info.username else None
    password = unquote(info.password) if info.password else None

    return RedisConnInfo(
        host=host,
        port=port,
        db=db,
        username=username,
        password=password,
        timeout_seconds=timeout_seconds,
    )


class RedisGateway:
    def __init__(self, redis_url: str, list_key: str, timeout_seconds: float) -> None:
        self._info = parse_redis_url(redis_url, timeout_seconds=timeout_seconds)
        self._list_key = list_key

    def lpush_json(self, payload_json: str) -> int:
        info = self._info
        with socket.create_connection((info.host, info.port), timeout=info.timeout_seconds) as sock:
            sock.settimeout(info.timeout_seconds)

            if info.password:
                if info.username and info.username != "default":
                    sock.sendall(
                        _resp_array(
                            [b"AUTH", info.username.encode("utf-8"), info.password.encode("utf-8")]
                        )
                    )
                else:
                    sock.sendall(_resp_array([b"AUTH", info.password.encode("utf-8")]))
                _expect_ok(sock)

            if info.db != 0:
                sock.sendall(_resp_array([b"SELECT", str(info.db).encode("utf-8")]))
                _expect_ok(sock)

            sock.sendall(
                _resp_array([b"LPUSH", self._list_key.encode("utf-8"), payload_json.encode("utf-8")])
            )
            return _read_int(sock)
