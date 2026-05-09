"""LLM client factory tests."""
import pytest

from llm.cloud_client import CloudClient
from llm.factory import get_llm, resolve_provider_kind
from llm.ollama_client import OllamaClient
from llm.provider_presets import build_provider_profile
from config import LLM_CONFIG


def test_resolve_provider_kind_maps_cloud_vendors_to_openai_compatible():
    assert resolve_provider_kind("openai") == "openai_compatible"
    assert resolve_provider_kind("deepseek") == "openai_compatible"
    assert resolve_provider_kind("custom") == "openai_compatible"


def test_resolve_provider_kind_maps_ollama():
    assert resolve_provider_kind("ollama") == "ollama"


def test_resolve_provider_kind_rejects_unknown_provider():
    with pytest.raises(ValueError):
        resolve_provider_kind("unknown")


def test_get_llm_returns_expected_client_types():
    assert isinstance(get_llm("ollama"), OllamaClient)
    assert isinstance(get_llm("openai"), CloudClient)
    assert isinstance(get_llm("deepseek"), CloudClient)


def test_get_llm_with_explicit_cloud_provider_does_not_mutate_runtime_config():
    original_vendor = LLM_CONFIG["openai"]["vendor"]

    client = get_llm("deepseek")

    assert isinstance(client, CloudClient)
    assert client.profile.vendor == "deepseek"
    assert LLM_CONFIG["openai"]["vendor"] == original_vendor


def test_get_llm_decodes_api_key_ref_without_storing_plaintext(monkeypatch):
    monkeypatch.setitem(LLM_CONFIG, "provider", "openai")
    monkeypatch.setitem(
        LLM_CONFIG,
        "openai",
        {"vendor": "openai", "api_key": "", "api_key_ref": "encrypted", "base_url": "https://api.example.com/v1", "model": "m"},
    )
    monkeypatch.setattr("llm.factory.decode_key", lambda value: "plain-secret")

    client = get_llm("openai")

    assert client.profile.api_key == "plain-secret"
    assert LLM_CONFIG["openai"]["api_key"] == ""


def test_cloud_client_builds_proxied_http_client_when_proxy_is_configured(monkeypatch):
    calls = {}

    def fake_default_async_httpx_client(**kwargs):
        calls["proxy_kwargs"] = kwargs
        return object()

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            calls["openai_kwargs"] = kwargs
            self.api_key = kwargs["api_key"]
            self.base_url = kwargs["base_url"]

    monkeypatch.setattr("llm.cloud_client.DefaultAsyncHttpxClient", fake_default_async_httpx_client)
    monkeypatch.setattr("llm.cloud_client.AsyncOpenAI", FakeAsyncOpenAI)

    client = CloudClient(
        build_provider_profile(
            {
                "vendor": "custom",
                "api_key": "secret",
                "base_url": "https://api.example.com/v1",
                "model": "demo-model",
                "proxy_url": "http://127.0.0.1:17890",
            }
        )
    )

    assert client.profile.proxy_url == "http://127.0.0.1:17890"
    assert calls["proxy_kwargs"]["proxy"] == "http://127.0.0.1:17890"
    assert calls["openai_kwargs"]["http_client"] is not None


def test_cloud_client_extract_text_accepts_plain_string_response():
    assert CloudClient._extract_text("hello") == "hello"


def test_cloud_client_extract_text_accepts_dict_chat_completion_shape():
    payload = {"choices": [{"message": {"content": "world"}}]}
    assert CloudClient._extract_text(payload) == "world"


def test_cloud_client_extract_text_accepts_object_chat_completion_shape():
    class Message:
        content = "object-text"

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    assert CloudClient._extract_text(Response()) == "object-text"


def test_cloud_client_extract_text_accepts_sse_chunk_with_delta_content():
    payload = (
        'data: {"choices":[{"delta":{"content":"hello "}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"world"}}]}\n\n'
        'data: [DONE]\n\n'
    )
    assert CloudClient._extract_text(payload) == "hello world"


def test_cloud_client_extract_text_rejects_sse_without_message_content():
    payload = (
        'data: {"id":"","object":"chat.completion.chunk","choices":[],"usage":{"completion_tokens":0}}\n\n'
        'data: [DONE]\n\n'
    )
    with pytest.raises(ValueError):
        CloudClient._extract_text(payload)
