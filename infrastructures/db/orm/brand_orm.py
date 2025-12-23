# -*- coding: utf-8 -*-
# @Author: yaccii
# @Description: 品牌研究数据表（外部任务/人工维护，本项目读取分析）

from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, Float, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from infrastructures.db.orm.orm_base import Base


class YsBrandORM(Base):
    __tablename__ = "src_brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="ID")
    brand_mark: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="品牌标识")
    brand_name: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="品牌名")
    brand_cate_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="品类")
    company_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="所属公司")
    investor: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="投资方")
    city: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="所在城市")
    stock_code: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="股票代码")
    logo: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="Logo")
    established_in: Mapped[int] = mapped_column(Integer, nullable=False, default=2000, comment="成立年份")
    parent_brand_name: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="父品牌")
    status: Mapped[str] = mapped_column(String(1), nullable=False, default="1", comment="状态:0=禁用,1=启用")
    weigh: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="权重(无实际业务意义)")
    updated_at: Mapped[int | None] = mapped_column("update_time", BigInteger, nullable=True, comment="更新时间")
    category1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    desc: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    __table_args__ = (
        UniqueConstraint("brand_name", name="uq_br_name"),
        Index("ix_br_mark", "brand_mark"),
    )


class YsBrandKeywordORM(Base):
    __tablename__ = "src_brand_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False, comment="关键词")
    brand_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="品牌ID")
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="查询时关联的关键词")
    created_at: Mapped[object | None] = mapped_column("create_time", DateTime, nullable=True, comment="创建时间")
    updated_at: Mapped[object | None] = mapped_column("update_time", DateTime, nullable=True, comment="更新时间")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="状态, 0禁用/1正常")

    __table_args__ = (
        Index("ix_bk_bid", "brand_id"),
    )


class YsBrandWebsiteORM(Base):
    __tablename__ = "src_brand_websites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="ID")
    brand_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="品牌ID")
    web_type: Mapped[str] = mapped_column(String(1), nullable=False, default="1", comment="网站类型:1独立站/2第三方平台")
    web_name: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="网站名称")
    web_url: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="域名")
    status: Mapped[str] = mapped_column(String(1), nullable=False, default="1", comment="状态:0禁用/1启用")
    updated_at: Mapped[int | None] = mapped_column("update_time", BigInteger, nullable=True, comment="更新时间")
    created_at: Mapped[int | None] = mapped_column("create_time", BigInteger, nullable=True, comment="创建时间")

    __table_args__ = (
        Index("ix_bw_bid", "brand_id"),
        Index("ix_bw_url", "web_url"),
    )


class YsBrandAmazonDataORM(Base):
    __tablename__ = "src_brand_amazon_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="ID")
    brand_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="品牌ID")
    keywords: Mapped[str] = mapped_column(String(128), nullable=False, comment="关键词")
    date_type: Mapped[str] = mapped_column(String(8), nullable=False, default="month", comment="日期类型:year/month/week/day")
    search_date: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="搜索日期")
    search_volume: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0, comment="搜索量")
    updated_at: Mapped[int | None] = mapped_column("update_time", BigInteger, nullable=True, comment="更新时间")
    created_at: Mapped[int | None] = mapped_column("create_time", BigInteger, nullable=True, comment="创建时间")

    __table_args__ = (
        UniqueConstraint("brand_id", "keywords", "date_type", "search_date", name="uq_ba_dim"),
        Index("ix_ba_bid", "brand_id"),
        Index("ix_ba_kw", "keywords"),
    )


class YsBrandGoogleDataORM(Base):
    __tablename__ = "src_brand_google_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="ID")
    brand_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="品牌ID")
    keywords: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="关键词")
    date_type: Mapped[str] = mapped_column(String(8), nullable=False, default="week", comment="日期类型:year/month/week/day")
    search_date: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="搜索日期")
    dt: Mapped[str | None] = mapped_column(String(16), nullable=True)
    search_volume: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0, comment="搜索量")
    updated_at: Mapped[int | None] = mapped_column("update_time", BigInteger, nullable=True, comment="更新时间")
    created_at: Mapped[int | None] = mapped_column("create_time", BigInteger, nullable=True, comment="创建时间")

    __table_args__ = (
        UniqueConstraint("brand_id", "keywords", "date_type", "search_date", name="uq_bg_dim"),
        Index("ix_bg_bid", "brand_id"),
        Index("ix_bg_kw", "keywords"),
    )


class YsBrandIndependenceDataORM(Base):
    __tablename__ = "src_brand_similarweb_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="ID")
    brand_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="ys_brand.id")
    website_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    web_url: Mapped[str] = mapped_column(String(512), nullable=False, comment="域名")

    date_type: Mapped[str] = mapped_column(String(8), nullable=False, default="month", comment="日期类型:year/month/week/day")
    search_date: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="搜索日期")
    search_volume: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0, comment="热度值")
    last_month: Mapped[str] = mapped_column(String(16), nullable=False, comment="月份")
    month_visits: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="月访问量")
    category: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="similarweb品类")

    direct: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="直接访问")
    direct_ratio: Mapped[float | None] = mapped_column(Float, nullable=True, comment="直接访问份额")
    referrals: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="外链访问")
    referrals_ratio: Mapped[float | None] = mapped_column(Float, nullable=True, comment="外链访问份额")
    organic_search: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="有机搜索")
    organic_search_ratio: Mapped[float | None] = mapped_column(Float, nullable=True, comment="有机搜索份额")
    paid_search: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="付费搜索")
    paid_search_ratio: Mapped[float | None] = mapped_column(Float, nullable=True, comment="付费搜索份额")
    social: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="社交")
    social_ratio: Mapped[float | None] = mapped_column(Float, nullable=True, comment="社交份额")
    email: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="邮箱")
    email_ratio: Mapped[float | None] = mapped_column(Float, nullable=True, comment="邮箱份额")
    display: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="展示广告")
    display_ratio: Mapped[float | None] = mapped_column(Float, nullable=True, comment="展示广告份额")

    country1: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country1_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    country2: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country2_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    country3: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country3_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    country4: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country4_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    country5: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country5_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    social1: Mapped[str | None] = mapped_column(String(64), nullable=True)
    social1_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    social2: Mapped[str | None] = mapped_column(String(64), nullable=True)
    social2_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    social3: Mapped[str | None] = mapped_column(String(64), nullable=True)
    social3_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    social4: Mapped[str | None] = mapped_column(String(64), nullable=True)
    social4_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    social5: Mapped[str | None] = mapped_column(String(64), nullable=True)
    social5_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    traffic_source: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="流量来源")
    created_at: Mapped[int | None] = mapped_column("create_time", BigInteger, nullable=True, comment="创建时间")
    updated_at: Mapped[int | None] = mapped_column("update_time", BigInteger, nullable=True, comment="更新时间")

    __table_args__ = (
        UniqueConstraint("brand_id", "web_url", "date_type", "search_date", name="uq_sw_dim"),
        Index("ix_sw_bm", "brand_id", "last_month"),
        Index("ix_sw_url", "web_url"),
    )
