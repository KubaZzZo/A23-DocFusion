"""LLM缓存测试"""
import pytest
from llm import cache
from llm.cache import get_cached, set_cached, clear_cache


class TestLLMCache:
    def setup_method(self):
        clear_cache()

    def teardown_method(self):
        clear_cache()

    def test_cache_miss(self):
        result = get_cached("prompt", "text")
        assert result is None

    def test_cache_hit(self):
        data = {"entities": [{"type": "person", "value": "张三"}]}
        set_cached("prompt", "text", data)
        result = get_cached("prompt", "text")
        assert result is not None
        assert result["entities"][0]["value"] == "张三"

    def test_different_input_no_hit(self):
        data = {"entities": []}
        set_cached("prompt1", "text1", data)
        result = get_cached("prompt2", "text2")
        assert result is None

    def test_cache_overwrite(self):
        set_cached("p", "t", {"v": 1})
        set_cached("p", "t", {"v": 2})
        result = get_cached("p", "t")
        assert result["v"] == 2

    def test_clear_cache(self):
        set_cached("p", "t", {"v": 1})
        clear_cache()
        result = get_cached("p", "t")
        assert result is None

    def test_memory_cache_is_bounded_and_evicts_lru(self, monkeypatch):
        monkeypatch.setattr(cache, "MAX_MEMORY_CACHE_SIZE", 2)
        clear_cache()
        set_cached("p1", "t", {"v": 1})
        set_cached("p2", "t", {"v": 2})
        get_cached("p1", "t")
        set_cached("p3", "t", {"v": 3})

        assert len(cache._memory_cache) == 2
        assert cache._hash_key("p1", "t") in cache._memory_cache
        assert cache._hash_key("p2", "t") not in cache._memory_cache

    def test_cache_key_uses_sha256(self):
        assert len(cache._hash_key("prompt", "text")) == 64

    def test_clear_cache_does_not_truncate_file_when_unlink_fails(self, monkeypatch, caplog):
        class LockedCacheFile:
            content = '{"safe": true}'
            wrote_empty = False

            def chmod(self, mode):
                pass

            def unlink(self):
                raise OSError("locked")

            def write_text(self, text, encoding="utf-8"):
                self.wrote_empty = True
                self.content = text

            def __str__(self):
                return "locked.json"

        class FakeCacheDir:
            def glob(self, pattern):
                return [cache_file]

        cache_file = LockedCacheFile()
        monkeypatch.setattr(cache, "CACHE_DIR", FakeCacheDir())

        clear_cache()

        assert cache_file.content == '{"safe": true}'
        assert cache_file.wrote_empty is False
        assert "Failed to clear cache file" in caplog.text
