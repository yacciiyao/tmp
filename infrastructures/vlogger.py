# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from infrastructures.vconfig import config


# request-scoped correlation id (optional)
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id_var.get()


def init_logging(level: str) -> None:
    """Initialize Python logging.

    Keep it boring: one formatter, one logger. If you need JSON logging later, add it later.
    """

    valid = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
    lvl = level.upper().strip()
    if lvl not in valid:
        lvl = "INFO"

    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = get_request_id()
        return record

    logging.setLogRecordFactory(record_factory)

    logging.basicConfig(
        level=getattr(logging, lvl),
        format="%(asctime)s %(levelname)s %(name)s [rid=%(request_id)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    # Ensure uvicorn logs go through root formatter
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "starlette"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True

    logger.info("logging initialized level=%s", lvl)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request_id and emit a single access log line per request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = "-"

        header_name = config.request_id_header
        incoming = request.headers.get(header_name)
        if incoming and incoming.strip():
            rid = incoming.strip()
        elif config.generate_request_id:
            rid = uuid.uuid4().hex

        token = _request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            _request_id_var.reset(token)

        # mirror back if we have a real rid
        if rid != "-":
            response.headers[header_name] = rid

        if config.log_requests:
            logger.info(
                "http %s %s -> %s %sms",
                request.method,
                request.url.path,
                getattr(response, "status_code", "?"),
                elapsed_ms,
            )
        return response


logger = logging.getLogger("app")
