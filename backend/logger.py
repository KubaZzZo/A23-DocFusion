"""统一日志配置"""
import logging
import sys
from pathlib import Path
from config import DATA_DIR

LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "docfusion.log"


def setup_logging(level=logging.INFO):
    """初始化日志系统"""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger("docfusion")
    root.setLevel(level)

    if root.handlers:
        return root

    # 控制台
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(fmt, datefmt))
    root.addHandler(console)

    # 文件
    file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt))
    root.addHandler(file_handler)

    return root


def get_logger(name: str) -> logging.Logger:
    """获取子模块logger"""
    return logging.getLogger(f"docfusion.{name}")
