from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import admin, auth, catalog, inventory, loans, reports, system, transactions


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="进销存管理系统 API",
    version="0.1.0",
    description="PC 桌面客户端使用的进销存管理 API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "inventory-sales-api"}


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(catalog.router)
app.include_router(transactions.router)
app.include_router(inventory.router)
app.include_router(loans.router)
app.include_router(reports.router)
app.include_router(system.router)

