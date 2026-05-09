"""全局配置"""
import os
from pathlib import Path


def _ensure_private_dir(path: Path) -> Path:
    path.mkdir(exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    if os.name == "nt":
        _restrict_windows_acl(path)
    return path


def _restrict_windows_acl(path: Path) -> None:
    import subprocess

    user = os.getenv("USERNAME")
    if not user:
        return
    try:
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        pass

# 项目根目录
BASE_DIR = Path(__file__).parent

# 数据目录
DATA_DIR = BASE_DIR / "data"
_ensure_private_dir(DATA_DIR)
UPLOAD_DIR = DATA_DIR / "uploads"
_ensure_private_dir(UPLOAD_DIR)
OUTPUT_DIR = DATA_DIR / "outputs"
_ensure_private_dir(OUTPUT_DIR)
CRAWLED_DIR = DATA_DIR / "crawled"
_ensure_private_dir(CRAWLED_DIR)

# 数据库
DB_PATH = DATA_DIR / "docfusion.db"

# LLM 配置
LLM_CONFIG = {
    "provider": os.getenv("LLM_PROVIDER", "ollama"),  # ollama / openai / custom
    "ollama": {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
    },
    "openai": {
        "vendor": os.getenv("OPENAI_VENDOR", "openai"),
        "api_key": "",
        "api_key_ref": "",
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    },
}

# 文本分块
CHUNK_SIZE = 3000  # 每块最大字符数
CHUNK_OVERLAP = 200  # 重叠字符数

# API服务
API_HOST = "127.0.0.1"
API_PORT = 8000
MAX_UPLOAD_SIZE = int(os.getenv("DOCFUSION_MAX_UPLOAD_SIZE", str(50 * 1024 * 1024)))

# 爬虫配置
CRAWLER_CONFIG = {
    "request_timeout": 15,
    "delay_min": 0.5,
    "delay_max": 1.5,
    "default_count": 10,
}

# OCR 配置
OCR_CONFIG = {
    "tesseract_cmd": os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    "lang": "chi_sim+eng",  # 中文简体+英文
}
