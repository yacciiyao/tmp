# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 众筹项目数据表（外部任务写入，本项目读取分析）

from __future__ import annotations

from sqlalchemy import Integer, String, Numeric, UniqueConstraint, Index, BigInteger, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from infrastructures.db.orm.orm_base import Base


class SrcProjectsORM(Base):
    __tablename__ = "src_cf_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="项目id")
    source: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="数据来源")
    project_id: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="第三方项目id")
    project_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="项目地址")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    project_type: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="项目类型")
    category: Mapped[str | None] = mapped_column(String(120), nullable=True, comment="一级分类")
    category2: Mapped[str | None] = mapped_column(String(120), nullable=True, comment="二级分类")
    title: Mapped[str | None] = mapped_column(String(300), nullable=True, comment="标题")
    title_desc: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="标题描述")

    owner_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True, comment="项目所在国家")
    city: Mapped[str | None] = mapped_column(String(120), nullable=True, comment="项目所在城市")
    currency: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="货币种类")
    to_usd_rate: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False, comment="转换美元汇率")

    funds_raised_amount: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True, comment="实际筹集金额")
    funds_plan_amount: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False, default=0.0,
                                                     comment="计划资金筹集金额")
    funds_raised_percent: Mapped[float | None] = mapped_column(Numeric(15, 6), nullable=True, comment="筹集百分比")
    comment_num: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="评论次数")
    updates_num: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="项目更新次数")
    backers_num: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="支持人数")
    product_stage: Mapped[str | None] = mapped_column(String(16), nullable=True)

    open_date: Mapped[int] = mapped_column(Integer, nullable=False, comment="项目开始时间")
    close_date: Mapped[int] = mapped_column(Integer, nullable=False, comment="项目关闭时间")
    update_date: Mapped[int] = mapped_column(Integer, nullable=False, comment="更新时间")
    create_date: Mapped[int] = mapped_column(Integer, nullable=False, comment="创建时间")

    __table_args__ = (
        UniqueConstraint("source", "project_id", name="uq_cf_sp"),
        Index("ix_cf_src", "source"),
        Index("ix_cf_pid", "project_id"),
    )


class SrcKickstarterProjectsORM(Base):
    __tablename__ = "src_cf_kickstarter_projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="自增ID")
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Kickstarter 原始项目ID")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="项目名称")
    blurb: Mapped[str | None] = mapped_column(Text, nullable=True, comment="项目简介")
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="项目slug")
    url_web_project: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="项目网页URL")
    url_web_rewards: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="奖励网页URL")
    photo: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="图片链接")
    state: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="项目状态")
    backers_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="支持人数")
    goal: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True, comment="筹资目标")
    pledged: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True, comment="已筹资金")
    country: Mapped[str | None] = mapped_column(String(8), nullable=True, comment="国家代码")
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True, comment="币种")
    currency_symbol: Mapped[str | None] = mapped_column(String(8), nullable=True, comment="币种符号")
    static_usd_rate: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True, comment="固定美元汇率")
    usd_pledged: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True, comment="美元筹资金额")
    fx_rate: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True, comment="汇率")
    usd_exchange_rate: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True, comment="美元汇率")
    converted_pledged_amount: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True,
                                                                   comment="转换后筹资金额(美元)")
    current_currency: Mapped[str | None] = mapped_column(String(8), nullable=True, comment="当前币种")
    usd_type: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="USD类型")
    percent_funded: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True, comment="百分比筹资")
    deadline: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="截止时间戳")
    state_changed_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="状态变更时间戳")
    created_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="创建时间戳")
    launched_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="上线时间戳")

    is_in_post_campaign_pledging_phase: Mapped[int | None] = mapped_column(Integer, nullable=True)
    staff_pick: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_starrable: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disable_communication: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spotlight: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_liked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_disliked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_launched: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prelaunch_activated: Mapped[int | None] = mapped_column(Integer, nullable=True)

    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_analytics_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_parent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    creator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creator_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creator_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creator_is_registered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creator_is_superbacker: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creator_backing_action_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    location_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_state: Mapped[str | None] = mapped_column(String(255), nullable=True)

    search_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    batch_no: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="批次号 YYYYMMDDHH")
    crawl_time: Mapped[object] = mapped_column(DateTime, nullable=False, comment="爬取时间")

    __table_args__ = (
        UniqueConstraint("project_id", "batch_no", name="uq_ks_pb"),
        Index("ix_ks_pid", "project_id"),
        Index("ix_ks_bno", "batch_no"),
    )


class SrcMakuakeProjectsORM(Base):
    __tablename__ = "src_cf_makuake_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    collected_money: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="応援購入総額")
    collected_supporter: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="サポーター")
    start_date: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="开始时间")
    expiration_date: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="结束时间")
    time_left_label: Mapped[str | None] = mapped_column(String(8), nullable=True, comment="残り")
    percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title_zh: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_coming_soon: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_store_opening: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_target_money: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_expiration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_accepting_support: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_new_store_opening: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hide_collected_money: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_selected_user: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    returns: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    crawl_time: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="所在页面")

    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="ストーリー")
    register_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goal: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="目標金額")
    activity_report: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="活動レポート")
    supporter: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="応援コメント")
    owner_rate: Mapped[float | None] = mapped_column(Numeric(2, 1), nullable=True, comment="実行者の総合評価（点数）")
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    like: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tag: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (
        UniqueConstraint("project_id", "batch_id", name="uq_mk_pb"),
        Index("ix_mk_pid", "project_id"),
        Index("ix_mk_bid", "batch_id"),
    )
