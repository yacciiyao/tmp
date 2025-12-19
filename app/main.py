# -*- coding: utf-8 -*-
# @File: main.py
# @Author: yaccii
# @Time: 2025-12-14 19:52
# @Description:

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, RedirectResponse

from app.routers import auth_router
from app.routers import rag_router
from domains.error_domain import AppError
from infrastructures.db.orm.orm_base import init_db, AsyncSessionFactory
from infrastructures.vconfig import config
from infrastructures.vlogger import init_logging, logger
from services.auth_service import AuthService
from infrastructures.db.repository.rag_repository import RagRepository


@asynccontextmanager
async def lifespan(_app: FastAPI):

    init_logging(config.log_level)

    # 1) 建表
    await init_db()
    logger.info("database schema ensured")

    # 2) 默认 admin
    async with AsyncSessionFactory() as db:
        auth_service = AuthService()
        await auth_service.ensure_default_admin(db)
    logger.info("default admin ensured")

    # 3) 默认 space（documents.kb_space 有外键约束，建议启动时保证 default 存在）
    repo = RagRepository()
    async with AsyncSessionFactory() as db:
        async with db.begin():
            existing = await repo.get_space(db, kb_space="default")
            if existing is None:
                await repo.create_space(db, kb_space="default", display_name="Default", description="default", enabled=1, status=1)
    logger.info("default space ensured")

    try:
        yield
    finally:
        logger.info("application shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Multi-Agent Hub",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # optional request context + access logging
    # app.add_middleware(RequestContextMiddleware)

    # ---------- Global error handler ----------
    @app.exception_handler(AppError)
    async def _app_error_handler(_req: Request, exc: AppError):
        return JSONResponse(status_code=exc.http_status, content=exc.to_response().model_dump())

    # ---------- CORS ----------
    cors = config.cors_origins.strip()
    if cors == "*":
        origins = ["*"]
    else:
        origins = [o.strip() for o in cors.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # # ---------- Static frontend ----------
    # app.mount("/web", StaticFiles(directory="web"), name="web")
    # app.mount("/static", StaticFiles(directory="web"), name="static")

    api = APIRouter(prefix="/api")

    @api.get("/health", tags=["system"])
    async def health_check():
        return {"status": "ok"}

    api.include_router(auth_router.router)
    api.include_router(rag_router.router)
    app.include_router(api)

    @app.get("/")
    async def index():
        return RedirectResponse(url="/web/chat.html", status_code=302)

    return app


app = create_app()
