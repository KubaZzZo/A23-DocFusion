import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.semantic_matcher import SemanticMatcher
from llm import cache as llm_cache
from llm.cloud_client import CloudClient
from llm.provider_presets import ProviderProfile


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


@pytest.mark.asyncio
async def test_cloud_client_falls_back_to_sse_text(monkeypatch):
    class FakeCompletions:
        async def create(self, **kwargs):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        api_key = "sk-test"
        chat = FakeChat()

    class FakeResponse:
        headers = {"content-type": "text/event-stream"}
        text = (
            'data: {"choices":[{"delta":{"content":"{\\"entities\\":"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"[]}"}}]}\n\n'
            "data: [DONE]\n\n"
        )

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("llm.cloud_client.httpx.AsyncClient", FakeAsyncClient)

    profile = ProviderProfile(
        vendor="custom",
        label="Custom",
        api_format="openai_compatible",
        api_key="sk-test",
        base_url="https://example.test/v1",
        model="test-model",
        proxy_url="",
    )
    client = CloudClient(profile)
    client.client = FakeOpenAI()

    result = await client.chat([{"role": "user", "content": "extract"}])

    assert result == '{"entities":[]}'
