"""LLM client factory tests."""
import pytest

from llm.cloud_client import CloudClient
from llm.factory import get_llm, resolve_provider_kind
from llm.ollama_client import OllamaClient
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
