"""LLM结果缓存 - 基于文本哈希的内存+文件缓存"""
import hashlib
import json
from pathlib import Path
from config import DATA_DIR

CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# 内存缓存
_memory_cache: dict[str, dict] = {}


def _hash_key(prompt: str, text: str) -> str:
    """生成缓存key"""
    content = f"{prompt}|||{text}"
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def get_cached(prompt: str, text: str) -> dict | None:
    """查询缓存，优先内存，其次文件"""
    key = _hash_key(prompt, text)

    # 内存缓存
    if key in _memory_cache:
        return _memory_cache[key]

    # 文件缓存
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            _memory_cache[key] = data
            return data
        except Exception:
            pass

    return None


def set_cached(prompt: str, text: str, result: dict):
    """写入缓存（内存+文件）"""
    key = _hash_key(prompt, text)
    _memory_cache[key] = result

    cache_file = CACHE_DIR / f"{key}.json"
    try:
        cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def clear_cache():
    """清空所有缓存"""
    _memory_cache.clear()
    for f in CACHE_DIR.glob("*.json"):
        try:
            f.chmod(0o666)
            f.unlink()
        except Exception:
            f.write_text("", encoding="utf-8")
