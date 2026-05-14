from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db
from backend.routers import balance, journal, books, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="账套管理系统 API",
    description="前后端分离的账套管理系统，支持科目余额表与序时账导入、查询、导出",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8001", "http://127.0.0.1:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(balance.router)
app.include_router(journal.router)
app.include_router(books.router)
app.include_router(export.router)


@app.get("/")
async def root():
    return {"message": "账套管理系统 API 服务运行中", "docs": "/docs"}