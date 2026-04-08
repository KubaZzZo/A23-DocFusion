"""FastAPI服务入口"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from db.models import init_db

app = FastAPI(
    title="DocFusion API",
    version="1.0.0",
    description="文档理解与多源数据融合系统API\n\n"
                "提供文档上传解析、实体提取、模板填写、新闻爬取等功能的RESTful接口。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


def start_api_server():
    """启动API服务（在子线程中调用）"""
    from config import API_HOST, API_PORT
    init_db()
    uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="info")


if __name__ == "__main__":
    start_api_server()
