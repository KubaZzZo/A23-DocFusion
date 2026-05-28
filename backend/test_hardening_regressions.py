import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.semantic_matcher import SemanticMatcher
from llm import cache as llm_cache


def test_llm_memory_cache_is_protected_by_lock():
    assert isinstance(llm_cache._memory_cache_lock, threading.RLock().__class__)


@pytest.mark.asyncio
async def test_semantic_matcher_prompt_contains_actual_fields_and_entities():
    captured = {}

    class FakeLLM:
        async def extract_json(self, prompt, user_input):
            captured["prompt"] = prompt
            return {"matches": [], "unmatched_fields": ["审批人"]}

    matcher = SemanticMatcher()
    matcher.llm = FakeLLM()

    await matcher.match([">审批人"], [{"type": "custom", "value": ">张三<", "confidence": 0.7}])

    assert ">审批人" in captured["prompt"]
    assert ">张三<" in captured["prompt"]
    assert "{fields}" not in captured["prompt"]
    assert "{entities}" not in captured["prompt"]
