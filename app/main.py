# -*- coding: utf-8 -*-
# @File: app/main.py
# @Author: yaccii
# @Description: FastAPI Application Entry

from __future__ import annotations

from importlib import import_module
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

from application.auth.auth_service import AuthService
from application.common.errors import AppError
from infrastructure import mlogger
from infrastructure.config import settings
from infrastructure.db.base import AsyncSessionFactory, init_db


def _include_router_safely(
    api: APIRouter,
    module_path: str,
    router_attr: str = "router",
    prefix: str = "",
    tags: Optional[list[str]] = None,
) -> None:
    """
    - 避免因为“某个 router 文件缺失/导入失败”导致整个应用启动失败
    - 必要模块仍建议在 CI 中保证存在；这里是运行期的韧性兜底
    """
    try:
        mod = import_module(module_path)
        router = getattr(mod, router_attr)
        api.include_router(router, prefix=prefix, tags=tags)
        mlogger.info("App", "router_loaded", module=module_path)
    except Exception as e:
        mlogger.warning("App", "router_skipped", module=module_path, error=str(e))


def create_app() -> FastAPI:
    app = FastAPI(
        title="Multi-Agent Hub",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # ---------- Global error handler ----------
    @app.exception_handler(AppError)
    async def _app_error_handler(_req: Request, exc: AppError):
        return JSONResponse(status_code=exc.http_status, content=exc.to_response().model_dump())

    # ---------- CORS ----------
    origins = settings.cors_origins or []
    # 若允许 "*"，则必须关闭 allow_credentials（否则浏览器拒绝）
    allow_credentials = settings.cors_allow_credentials if origins != ["*"] else False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else [],
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------- Static frontend ----------
    # 兼容两种前缀：/web 与 /static（你当前 index 重定向用到了 /static，但 mount 用的是 /web）
    app.mount("/web", StaticFiles(directory="web"), name="web")
    app.mount("/static", StaticFiles(directory="web"), name="static")

    api = APIRouter(prefix="/api")

    @api.get("/health", tags=["system"])
    async def health_check():
        return {"status": "ok"}

    # 核心业务路由（缺失则跳过并告警）
    _include_router_safely(api, "app.routers.auth_router")
    _include_router_safely(api, "app.routers.chat_router")
    _include_router_safely(api, "app.routers.rag_router")
    _include_router_safely(api, "app.routers.model_router")

    # 可选业务路由（存在即加载）
    _include_router_safely(api, "app.routers.agent_router", prefix="/agents", tags=["agents"])
    _include_router_safely(api, "app.routers.brand_router", prefix="/brands", tags=["brands"])
    _include_router_safely(api, "app.routers.project_router", prefix="/projects", tags=["projects"])
    _include_router_safely(api, "app.routers.file_router", prefix="/files", tags=["files"])
    _include_router_safely(api, "app.routers.amazon_router", prefix="/amazon", tags=["amazon"])

    app.include_router(api)

    @app.get("/")
    async def index():
        # 优先跳到 /web；/static 也可用
        return RedirectResponse(url="/web/chat.html", status_code=302)

    @app.on_event("startup")
    async def on_startup() -> None:
        mlogger.configure_logging(settings.log_level)

        # 1) 建表
        await init_db()
        mlogger.info("App", "startup", msg="database schema ensured")

        # 2) 默认 admin
        async with AsyncSessionFactory() as db:
            auth_service = AuthService()
            await auth_service.ensure_default_admin(db)
        mlogger.info("App", "startup", msg="default admin ensured")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        mlogger.info("App", "shutdown", msg="application shutdown")

    return app


app = create_app()
