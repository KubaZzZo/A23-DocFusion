"""DocFusion - 文档理解与多源数据融合系统 入口"""
import sys
import os

# 确保项目根目录在path中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.models import init_db
from logger import setup_logging, get_logger
from ui.settings_dialog import apply_saved_settings


def main():
    # 初始化日志
    setup_logging()
    log = get_logger("main")
    log.info("DocFusion 启动中...")

    # 加载持久化设置
    apply_saved_settings()
    log.info("配置加载完成")

    # 初始化数据库
    init_db()
    log.info("数据库初始化完成")

    # 启动桌面应用
    from ui.main_window import run_app
    run_app()


if __name__ == "__main__":
    main()
