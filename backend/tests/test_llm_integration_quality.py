import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.entity_extractor import EntityExtractor
from llm.base import BaseLLM
from llm.cloud_client import CloudClient


class CapturingLLM(BaseLLM):
    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.messages = []

    async def chat(self, messages, temperature=0.1):
        self.messages.append(messages)
        return '{"entities":[],"summary":"ok","topic":"demo"}'


def test_extract_json_places_schema_in_system_and_text_only_in_user_message():
    llm = CapturingLLM()
    text = f"raw contract text {uuid.uuid4()}"

    import asyncio

    asyncio.run(llm.extract_json("schema: {entities: []}", text))

    messages = llm.messages[0]
    assert "schema: {entities: []}" in messages[0]["content"]
    assert text not in messages[0]["content"]
    assert text in messages[1]["content"]
    assert "schema: {entities: []}" not in messages[1]["content"]


def test_prompt_profile_uses_concise_for_small_models_and_detailed_for_cloud_models():
    small = EntityExtractor(prompt_profile="auto")
    small.llm = CapturingLLM(model="qwen2.5:7b")
    large = EntityExtractor(prompt_profile="auto")
    large.llm = CapturingLLM(model="gpt-4o")

    assert small._prompt_profile() == "concise"
    assert large._prompt_profile() == "detailed"


@pytest.mark.asyncio
async def test_entity_extractor_reports_chunk_progress(monkeypatch):
    events = []

    class FakeChunker:
        def chunk(self, text):
            return ["chunk one amount 100", "chunk two date 2026-01-01"]

    extractor = EntityExtractor(enable_verify=False)
    extractor.chunker = FakeChunker()
    extractor.llm = CapturingLLM()

    await extractor.extract("long text", force=True, progress=events.append)

    assert events[0]["stage"] == "started"
    assert any(event["stage"] == "chunk" and event["current"] == 1 for event in events)
    assert events[-1]["stage"] == "completed"


@pytest.mark.asyncio
async def test_cloud_client_retries_transient_errors(monkeypatch):
    calls = []

    class FakeCompletions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) < 3:
                raise RuntimeError("429 rate limit")
            return {"choices": [{"message": {"content": "ok"}}]}

    client = CloudClient.__new__(CloudClient)
    client.profile = type("Profile", (), {"vendor": "openai", "label": "OpenAI"})()
    client.model = "gpt-4o"
    client.client = type(
        "FakeClient",
        (),
        {"api_key": "sk-test", "base_url": "https://example.test", "chat": type("Chat", (), {"completions": FakeCompletions()})()},
    )()
    async def no_sleep(delay):
        return None

    monkeypatch.setattr("llm.cloud_client.asyncio.sleep", no_sleep)

    result = await client.chat([{"role": "user", "content": "hi"}])

    assert result == "ok"
    assert len(calls) == 3
