"""FastAPI服务入口"""
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import public_router, router
from db.models import init_db
from settings_store import apply_saved_settings


def initialize_runtime() -> None:
    """Apply disk-backed settings and prepare storage when the service starts."""
    apply_saved_settings()
    init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_runtime()
    yield


app = FastAPI(
    title="DocFusion API",
    version="1.0.0",
    description="文档理解与多源数据融合系统API\n\n"
                "提供文档上传解析、实体提取、模板填写、新闻爬取等功能的RESTful接口。",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1",
        "http://127.0.0.1:8000",
        "http://localhost",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router)
app.include_router(router)


def start_api_server():
    """启动API服务（在子线程中调用）"""
    from config import API_HOST, API_PORT
    uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="info")


if __name__ == "__main__":
    start_api_server()
