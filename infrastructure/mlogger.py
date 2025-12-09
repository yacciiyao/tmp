# -*- coding: utf-8 -*-
# @File: mlogger.py
# @Author: yaccii
# @Description:
from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger("multi_agent_hub")


def configure_logging(level: str = "INFO") -> None:
    """
    在应用启动时调用一次。
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    _logger.setLevel(numeric_level)

    # 压制 SQLAlchemy & aiomysql 的详细日志，只保留 WARNING+
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("aiomysql").setLevel(logging.WARNING)


def _format_message(component: str, action: str, **fields: Any) -> str:
    if fields:
        kv = " ".join(f"{k}={v!r}" for k, v in fields.items())
        return f"{component}.{action} | {kv}"
    return f"{component}.{action}"


def debug(component: str, action: str, **fields: Any) -> None:
    _logger.debug(_format_message(component, action, **fields))


def info(component: str, action: str, **fields: Any) -> None:
    _logger.info(_format_message(component, action, **fields))


def warning(component: str, action: str, **fields: Any) -> None:
    _logger.warning(_format_message(component, action, **fields))


def error(component: str, action: str, **fields: Any) -> None:
    _logger.error(_format_message(component, action, **fields))


def exception(component: str, action: str, **fields: Any) -> None:
    _logger.exception(_format_message(component, action, **fields))
