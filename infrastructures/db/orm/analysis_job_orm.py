# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 分析任务表（报告/诊断等统一作业模型）

from __future__ import annotations

from typing import Any

from sqlalchemy import Integer, JSON, ForeignKey, String, Index, Text
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from infrastructures.db.orm.orm_base import TimestampMixin, Base


class OpsAnalysisJobsORM(TimestampMixin, Base):
    __tablename__ = "ops_analysis_jobs"

    job_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="任务ID(自增)")
    job_type: Mapped[int] = mapped_column(Integer, nullable=False, comment="任务类型（AnalysisJobType）")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=10,
                                        comment="状态：10待执行/20执行中/30成功/40失败")

    payload: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
        comment="任务输入（结构化）",
    )
    trace: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
        comment="可回溯信息（来源/筛选条件/版本等）",
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
        comment="任务结果（结构化）",
    )

    spider_task_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ops_spider_tasks.task_id"),
        nullable=True,
        comment="关联爬虫任务ID（可选）",
    )

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="错误码")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")

    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("meta_users.user_id"),
        nullable=True,
        comment="创建人用户ID",
    )


Index("ix_aj_type_st", OpsAnalysisJobsORM.job_type, OpsAnalysisJobsORM.status)
Index("ix_aj_spid", OpsAnalysisJobsORM.spider_task_id)
Index("ix_aj_cby", OpsAnalysisJobsORM.created_by)
