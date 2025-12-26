# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: VOC tables (jobs / spider_tasks / reports)

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from infrastructures.db.orm.orm_base import Base, TimestampMixin


class OpsVocJobsORM(TimestampMixin, Base):
    """VOC 作业表（业务库 app_db）"""

    __tablename__ = "ops_voc_jobs"

    job_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="VOC作业ID(自增)")
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="作业类型(review_analysis/...) ")

    site_code: Mapped[str] = mapped_column(String(16), nullable=False, comment="站点代码，如 US/DE/JP")
    asin: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="asin（review/listing 用）")
    keyword: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="关键词（keyword/market 用）")
    category: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="类目（market 用）")

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        comment="状态：10待执行/20执行中/30成功/40失败/50取消",
    )

    try_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已重试次数")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, comment="最大重试次数")

    locked_by: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="锁持有者(worker)")
    locked_until: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="锁过期时间戳(秒)")

    report_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="报告ID（ops_voc_reports.report_id）")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="最近一次错误信息")

    created_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("meta_users.user_id"),
        nullable=True,
        comment="创建者 user_id（可空）",
    )

    __table_args__ = (
        Index("ix_voc_job_lock", "status", "locked_until"),
        Index("ix_voc_job_type_site_asin", "job_type", "site_code", "asin"),
        Index("ix_voc_job_type_site_keyword", "job_type", "site_code", "keyword"),
        Index("ix_voc_job_type_site_category", "job_type", "site_code", "category"),
    )


class OpsVocJobSpiderTasksORM(TimestampMixin, Base):
    """VOC 爬虫任务表（业务库 app_db）"""

    __tablename__ = "ops_voc_job_spider_tasks"

    task_row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="任务行ID(自增)")
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("ops_voc_jobs.job_id"), nullable=False, comment="VOC作业ID")

    task_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="爬虫任务ID（回调定位，唯一）")

    # one-time callback token per task (store hash only)
    callback_token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        comment="callback token sha256 hex（每task唯一；不存明文）",
    )
    callback_token_created_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="token生成时间(epoch秒)",
    )
    run_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="爬虫运行类型，如 amazon_review")

    site_code: Mapped[str] = mapped_column(String(16), nullable=False, comment="站点代码")
    asin: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="asin（review/listing）")
    keyword: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="关键词（keyword/market）")
    category: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="类目（market）")

    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        comment="状态：10待爬/20爬取中/30就绪/40失败",
    )
    run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="results库的 run_id（SSOT绑定点）")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="最近一次错误信息")

    __table_args__ = (
        UniqueConstraint("task_id", name="uq_voc_task_id"),
        Index("ix_voc_task_job", "job_id"),
        Index("ix_voc_task_status", "status"),
    )


class OpsVocReportsORM(TimestampMixin, Base):
    """VOC 报告表（业务库 app_db）"""

    __tablename__ = "ops_voc_reports"

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="报告ID(自增)")
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ops_voc_jobs.job_id"),
        nullable=False,
        comment="VOC作业ID（一作业一报告）",
    )

    report_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="报告类型，如 review_analysis")

    payload_json: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
        comment="报告payload(JSON)",
    )
    meta_json: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
        comment="报告meta(JSON)",
    )

    __table_args__ = (
        UniqueConstraint("job_id", name="uq_voc_report_job"),
        Index("ix_voc_report_type", "report_type"),
    )
