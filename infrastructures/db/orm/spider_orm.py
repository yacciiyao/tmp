# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 爬虫任务表（本项目只负责触发与读取结果）

from __future__ import annotations

from typing import Any

from sqlalchemy import Integer, String, JSON, ForeignKey, Index, Text
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column

from infrastructures.db.orm.orm_base import TimestampMixin, Base


class OpsSpiderTasksORM(TimestampMixin, Base):
    __tablename__ = "ops_spider_tasks"

    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="任务ID(自增)")
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="任务类型，如 amazon.collect")
    task_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="任务Key（幂等）")
    biz: Mapped[str] = mapped_column(String(32), nullable=False, comment="业务域：amazon/brand/crowdfunding")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=10, comment="状态：10创建/20入队/30就绪/40失败")

    payload: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
        comment="发送给爬虫的结构化参数",
    )
    result_tables: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
        comment="期望写入的结果表名列表",
    )
    result_locator: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
        comment="结果定位信息（如 crawl_batch_no）",
    )

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="错误码")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")

    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("meta_users.user_id"),
        nullable=True,
        comment="创建人用户ID",
    )


Index("uq_sp_tkey", OpsSpiderTasksORM.task_key, unique=True)
Index("ix_sp_type_st", OpsSpiderTasksORM.task_type, OpsSpiderTasksORM.status)
Index("ix_sp_biz_st", OpsSpiderTasksORM.biz, OpsSpiderTasksORM.status)
Index("ix_sp_cby", OpsSpiderTasksORM.created_by)
