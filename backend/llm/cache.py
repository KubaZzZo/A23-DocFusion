"""LLM结果缓存 - 基于文本哈希的内存+文件缓存"""
import hashlib
import json
import logging
import threading
from collections import OrderedDict
from pathlib import Path
from config import DATA_DIR

CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)
log = logging.getLogger(__name__)

# 内存缓存
MAX_MEMORY_CACHE_SIZE = 300
_memory_cache: OrderedDict[str, dict] = OrderedDict()
_memory_cache_lock = threading.RLock()


def _remember(key: str, data: dict):
    with _memory_cache_lock:
        _memory_cache[key] = data
        _memory_cache.move_to_end(key)
        while len(_memory_cache) > MAX_MEMORY_CACHE_SIZE:
            _memory_cache.popitem(last=False)


def _hash_key(prompt: str, text: str) -> str:
    """生成缓存key"""
    content = f"{prompt}|||{text}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_cached(prompt: str, text: str) -> dict | None:
    """查询缓存，优先内存，其次文件"""
    key = _hash_key(prompt, text)

    # 内存缓存
    with _memory_cache_lock:
        if key in _memory_cache:
            _memory_cache.move_to_end(key)
            return _memory_cache[key]

    # 文件缓存
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            _remember(key, data)
            return data
        except Exception:
            pass

    return None


def set_cached(prompt: str, text: str, result: dict):
    """写入缓存（内存+文件）"""
    key = _hash_key(prompt, text)
    _remember(key, result)

    cache_file = CACHE_DIR / f"{key}.json"
    try:
        cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def clear_cache():
    """清空所有缓存"""
    with _memory_cache_lock:
        _memory_cache.clear()
    for f in CACHE_DIR.glob("*.json"):
        try:
            f.chmod(0o666)
            f.unlink()
        except Exception:
            log.warning("Failed to clear cache file %s", f)
