"""LLM缓存测试"""
import pytest
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
