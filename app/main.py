# -*- coding: utf-8 -*-
# @File: app/main.py
# @Author: yaccii
# @Description: FastAPI Application Entry

from __future__ import annotations

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

from infrastructure import mlogger
from infrastructure.config import settings
from infrastructure.db.base import init_db, AsyncSessionFactory

# 业务服务：默认管理员
from application.auth.auth_service import AuthService

# 业务路由：逐个显式导入，避免 __init__ 重导出带来的不确定性
from app.routers.auth_router import router as auth_router
from app.routers.chat_router import router as chat_router
from app.routers.rag_router import router as rag_router
from app.routers.model_router import router as model_router
# 如存在以下路由文件则会成功导入，若你的项目尚未提供，可先注释

# ---------------------------------------------------------------------

app = FastAPI(
    title="Multi-Agent Hub",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态资源：前端页面
app.mount("/web", StaticFiles(directory="web"), name="static")

# 统一 API 前缀
api = APIRouter(prefix="/api")

# 健康检查（统一到 /api/health）
@api.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok"}

# 业务路由全部挂到 /api 下
api.include_router(auth_router)
api.include_router(chat_router)
api.include_router(rag_router)
api.include_router(model_router)

# 如有以下模块，则同时纳入 /api
# api.include_router(agent_router, prefix="/agents", tags=["agents"])
# api.include_router(brand_router, prefix="/brands", tags=["brands"])
# api.include_router(project_router, prefix="/projects", tags=["projects"])
# api.include_router(file_router, prefix="/files", tags=["files"])
# api.include_router(amazon_router, prefix="/amazon", tags=["amazon"])

# 将 /api* 装载到应用
app.include_router(api)

# 根路径重定向到静态页面（可选）
@app.get("/")
async def index():
    return RedirectResponse(url="/static/chat.html", status_code=302)

# -------------------- 生命周期钩子 --------------------

@app.on_event("startup")
async def on_startup() -> None:
    mlogger.configure_logging(settings.log_level)

    # 1. 建表
    await init_db()
    mlogger.info("App", "startup", msg="database schema ensured")

    # 2. 确保默认 admin 存在
    async with AsyncSessionFactory() as db:
        auth_service = AuthService()
        await auth_service.ensure_default_admin(db)
    mlogger.info("App", "startup", msg="default admin ensured")

@app.on_event("shutdown")
async def on_shutdown() -> None:
    mlogger.info("App", "shutdown", msg="application shutdown")
