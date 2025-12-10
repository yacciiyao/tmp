# -*- coding: utf-8 -*-
# @File: app/main.py
# @Author: yaccii
# @Description: FastAPI Application Entry

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    auth_router,
    chat_router,
    rag_router,
    model_router,
    agent_router,
    brand_router,
    project_router,
    amazon_router,
)

from application.auth.auth_service import AuthService
from infrastructure import mlogger
from infrastructure.db.base import init_db, AsyncSessionFactory


app = FastAPI(
    title="Multi-Agent Hub",
    version="0.1.0",
)

# -------------------- CORS --------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 之后按需要收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Routers --------------------

app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(rag_router.router)
app.include_router(model_router.router)
# app.include_router(agent_router.router)
# app.include_router(brand_router.router)
# app.include_router(project_router.router)
# app.include_router(amazon_router.router)


# -------------------- Lifecycle --------------------

@app.on_event("startup")
async def on_startup() -> None:
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


# -------------------- Health Check --------------------

@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok"}
